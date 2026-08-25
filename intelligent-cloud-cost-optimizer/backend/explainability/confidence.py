"""
Confidence Scorer.
Computes an overall confidence score for a recommendation
based on data quality, model agreement, security, and risk.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceBreakdown:
    overall: float                  # 0-100
    data_quality: float
    model_agreement: float
    security_confidence: float
    risk_confidence: float
    label: str                      # Low | Medium | High | Very High
    explanation: str


class ConfidenceScorer:
    """Produces an interpretable confidence score for AI recommendations."""

    WEIGHTS = {
        "data_quality":        0.30,
        "model_agreement":     0.30,
        "security_confidence": 0.20,
        "risk_confidence":     0.20,
    }

    def score(self, recommendation: Dict[str, Any], forecast_data: Dict[str, Any]) -> ConfidenceBreakdown:
        dq  = self._data_quality_score(recommendation, forecast_data)
        ma  = self._model_agreement_score(forecast_data)
        sc  = self._security_confidence(recommendation)
        rc  = self._risk_confidence(recommendation)

        overall = (
            dq  * self.WEIGHTS["data_quality"]        +
            ma  * self.WEIGHTS["model_agreement"]      +
            sc  * self.WEIGHTS["security_confidence"]  +
            rc  * self.WEIGHTS["risk_confidence"]
        )
        overall = round(min(99.0, max(30.0, overall)), 1)

        return ConfidenceBreakdown(
            overall=overall,
            data_quality=round(dq, 1),
            model_agreement=round(ma, 1),
            security_confidence=round(sc, 1),
            risk_confidence=round(rc, 1),
            label=self._label(overall),
            explanation=self._explain(overall, dq, ma, sc, rc),
        )

    def _data_quality_score(self, rec: Dict, fc: Dict) -> float:
        """Higher if we have 12 months of data and no gaps."""
        history_months = fc.get("history_months", 12)
        anomaly_count  = len(fc.get("anomalies", []))
        base = min(100, history_months / 12 * 100)
        penalty = min(30, anomaly_count * 5)
        return max(40, base - penalty)

    def _model_agreement_score(self, fc: Dict) -> float:
        """Higher when ARIMA, Prophet, and XGBoost agree closely."""
        sub = fc.get("sub_model_predictions", {})
        if len(sub) < 2:
            return 75.0
        preds = list(sub.values())
        mean_pred = sum(preds) / len(preds)
        if mean_pred == 0:
            return 75.0
        cv = (sum(abs(p - mean_pred) for p in preds) / len(preds)) / mean_pred
        return max(40, min(100, 100 - cv * 200))

    def _security_confidence(self, rec: Dict) -> float:
        score = rec.get("security_score", 80)
        approved = rec.get("security_approved", True)
        if not approved:
            return 20.0
        return min(100, score)

    def _risk_confidence(self, rec: Dict) -> float:
        expl = rec.get("explanation", {})
        risk_score = expl.get("risk", {}).get("overall_score", 30)
        # Low risk → high confidence
        return max(20, 100 - risk_score)

    @staticmethod
    def _label(score: float) -> str:
        if score >= 90: return "Very High"
        if score >= 75: return "High"
        if score >= 60: return "Medium"
        return "Low"

    @staticmethod
    def _explain(overall, dq, ma, sc, rc) -> str:
        parts = []
        if dq >= 80:  parts.append("strong historical data")
        else:          parts.append("limited historical data")
        if ma >= 80:  parts.append("high model agreement")
        elif ma < 60:  parts.append("models show variance")
        if sc >= 80:  parts.append("security checks passed")
        else:          parts.append("security concerns present")
        if rc >= 70:  parts.append("low migration risk")
        return f"Confidence {overall:.0f}% based on: {', '.join(parts)}."

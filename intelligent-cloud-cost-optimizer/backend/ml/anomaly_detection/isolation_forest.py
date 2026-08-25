"""
Isolation Forest Anomaly Detector.
Detects unusual cost spikes across cloud resources using sklearn IsolationForest.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    resource_id: str
    provider: str
    anomaly_type: str
    severity: str            # low | medium | high | critical
    score: float             # isolation score (higher = more anomalous)
    description: str
    detected_value: float
    expected_range: tuple
    detected_at: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)


class IsolationForestDetector:
    """
    Detects cost and usage anomalies using Isolation Forest.
    Works on a per-resource time series of costs or metrics.
    """

    def __init__(self, contamination: float = 0.05, random_state: int = 42):
        self.contamination = contamination
        self.random_state  = random_state
        self._model = None

    def fit(self, data: List[float]) -> None:
        """Train on historical cost values."""
        from sklearn.ensemble import IsolationForest
        X = np.array(data).reshape(-1, 1)
        self._model = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100,
        )
        self._model.fit(X)
        logger.info("IsolationForest fitted on %d samples.", len(data))

    def detect(
        self,
        resource_id: str,
        provider: str,
        dates: List[str],
        values: List[float],
        metric_name: str = "cost",
    ) -> List[AnomalyResult]:
        """Detect anomalies in a resource time series."""
        if len(values) < 5:
            return []

        self.fit(values)
        X = np.array(values).reshape(-1, 1)
        labels  = self._model.predict(X)       # -1 = anomaly, 1 = normal
        scores  = self._model.decision_function(X)  # more negative = more anomalous
        anomaly_score = -scores  # flip so higher = more anomalous

        mean_val = float(np.mean(values))
        std_val  = float(np.std(values))
        results  = []

        for i, label in enumerate(labels):
            if label == -1:
                val    = values[i]
                z_score = abs(val - mean_val) / max(std_val, 1)
                severity = self._severity(z_score)
                direction = "spike" if val > mean_val else "drop"

                results.append(AnomalyResult(
                    resource_id=resource_id,
                    provider=provider,
                    anomaly_type=f"{metric_name}_{direction}",
                    severity=severity,
                    score=round(float(anomaly_score[i]), 4),
                    description=(
                        f"{metric_name.replace('_', ' ').title()} {direction} detected on "
                        f"{dates[i]}: ₹{val:,.0f} vs expected ₹{mean_val:,.0f} "
                        f"(z-score={z_score:.1f})"
                    ),
                    detected_value=round(val, 2),
                    expected_range=(
                        round(mean_val - 2 * std_val, 2),
                        round(mean_val + 2 * std_val, 2),
                    ),
                    detected_at=datetime.utcnow(),
                    details={
                        "date": dates[i],
                        "z_score": round(z_score, 2),
                        "mean": round(mean_val, 2),
                        "std": round(std_val, 2),
                    },
                ))

        logger.info("IsolationForest found %d anomalies in %s.", len(results), resource_id)
        return results

    def detect_multi_resource(
        self, resources: List[Dict[str, Any]]
    ) -> List[AnomalyResult]:
        """Run detection across multiple resources."""
        all_anomalies = []
        for res in resources:
            anomalies = self.detect(
                resource_id=res.get("resource_id", "unknown"),
                provider=res.get("provider", "unknown"),
                dates=res.get("dates", []),
                values=res.get("values", []),
                metric_name=res.get("metric", "cost"),
            )
            all_anomalies.extend(anomalies)
        return sorted(all_anomalies, key=lambda a: a.score, reverse=True)

    @staticmethod
    def _severity(z_score: float) -> str:
        if z_score > 4:   return "critical"
        if z_score > 3:   return "high"
        if z_score > 2:   return "medium"
        return "low"

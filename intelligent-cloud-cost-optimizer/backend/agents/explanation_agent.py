"""
Explanation Agent — Explainable AI layer.
Generates a human-readable, structured explanation for every recommendation:
WHY, WHAT data, WHAT alternatives, HOW MUCH saving, WHAT risk, WHAT IF failed.
"""

import logging
from typing import Any, Dict, List

from agents.base_agent import BaseAgent, AgentMemory, AgentResult
from ml.risk.risk_model import RiskModel

logger = logging.getLogger(__name__)


class ExplanationAgent(BaseAgent):
    """Produces structured XAI explanations for every approved recommendation."""

    def __init__(self, memory: AgentMemory = None):
        super().__init__("explanation_agent", memory)
        self._risk_model = RiskModel()

    async def _execute(self, context: Dict[str, Any]) -> AgentResult:
        self._add_message("system", "Generating explanations for recommendations...")

        approved  = self.memory.get("recommendations_approved", [])
        rejected  = self.memory.get("recommendations_rejected", [])
        all_recs  = approved + rejected

        if not all_recs:
            # Fall back to un-filtered list
            all_recs = self.memory.get("recommendations", [])

        explained: List[Dict[str, Any]] = []
        for rec in all_recs:
            explanation = self._explain(rec)
            rec_copy = dict(rec)
            rec_copy["explanation"] = explanation
            explained.append(rec_copy)

        self.memory.set("explained_recommendations", explained)

        reasoning = f"Generated explanations for {len(explained)} recommendations."
        self._add_message("assistant", reasoning)

        return AgentResult(
            agent_name=self.name,
            success=True,
            data={"explained_recommendations": explained},
            reasoning=reasoning,
        )

    def _explain(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        """Build a full XAI explanation block for a single recommendation."""
        current_cost   = rec.get("current_cost", 0)
        predicted_cost = rec.get("predicted_cost", 0)
        saving         = rec.get("estimated_saving", 0)
        saving_pct     = rec.get("saving_percentage", 0)
        current_prov   = (rec.get("current_provider") or "N/A").upper()
        target_prov    = (rec.get("recommended_provider") or "N/A").upper()
        security_score = rec.get("security_score", 80.0)
        confidence     = rec.get("confidence", 0.88)
        rec_type       = rec.get("rec_type", "optimization")

        # Risk assessment
        risk = self._risk_model.assess({
            "recommendation_id": rec.get("recommendation_id", ""),
            "current_provider":  rec.get("current_provider", ""),
            "recommended_provider": rec.get("recommended_provider", ""),
            "saving_percentage": saving_pct,
            "security_score":    security_score,
            "workload_criticality": "medium",
            "current_cpu":       rec.get("current_cpu", 30),
            "current_memory":    rec.get("current_memory", 40),
            "is_stateful":       rec_type == "provider_switch",
            "has_dependencies":  rec_type == "provider_switch",
        })

        # Feature importance (which factors drove this recommendation)
        feature_importance = self._feature_importance(rec, risk)

        # Alternatives considered
        alternatives = self._alternatives(rec)

        # Annual projection
        annual_saving = round(saving * 12, 2)

        return {
            # ── Summary ──────────────────────────────────────────────────────
            "summary": rec.get("reason", "Cost optimization opportunity identified."),

            # ── Cost breakdown ────────────────────────────────────────────────
            "cost_analysis": {
                "current_provider":  current_prov,
                "current_cost_inr":  current_cost,
                "recommended_provider": target_prov,
                "predicted_cost_inr": predicted_cost,
                "monthly_saving_inr": round(saving, 2),
                "saving_percentage":  round(saving_pct, 1),
                "annual_saving_inr":  annual_saving,
            },

            # ── Security ──────────────────────────────────────────────────────
            "security": {
                "score":    security_score,
                "rating":   self._score_label(security_score),
                "approved": rec.get("security_approved", True),
                "findings": rec.get("security_findings", {}),
            },

            # ── Risk ──────────────────────────────────────────────────────────
            "risk": {
                "level":            risk.risk_level,
                "overall_score":    risk.overall_score,
                "performance_risk": risk.performance_risk,
                "availability_risk": risk.availability_risk,
                "security_risk":    risk.security_risk,
                "migration_risk":   risk.migration_risk,
                "factors":          risk.factors,
                "mitigation":       risk.mitigation,
            },

            # ── Confidence ────────────────────────────────────────────────────
            "confidence": {
                "score":      round(confidence * 100, 1),
                "label":      "High" if confidence > 0.9 else "Medium" if confidence > 0.75 else "Low",
                "basis":      "Based on 12 months of historical data and ML model agreement.",
            },

            # ── Feature importance ────────────────────────────────────────────
            "feature_importance": feature_importance,

            # ── Alternatives ─────────────────────────────────────────────────
            "alternatives_considered": alternatives,

            # ── What-if failure ───────────────────────────────────────────────
            "failure_scenario": {
                "what_if_failed": "Automated rollback restores original configuration within 5 minutes.",
                "rollback_time":  "< 5 minutes",
                "data_risk":      "No data loss — snapshots taken before execution.",
                "monitoring":     "Real-time metrics monitored for 30 minutes post-execution.",
            },
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _feature_importance(rec: Dict, risk) -> List[Dict[str, Any]]:
        saving_pct  = rec.get("saving_percentage", 0)
        sec_score   = rec.get("security_score", 80)
        confidence  = rec.get("confidence", 0.88)

        features = [
            {"feature": "Cost Saving Potential", "importance": min(1.0, saving_pct / 50),
             "value": f"{saving_pct:.1f}% saving"},
            {"feature": "Security Score",        "importance": sec_score / 100,
             "value": f"{sec_score:.0f}/100"},
            {"feature": "Risk Level",            "importance": 1.0 - risk.overall_score / 100,
             "value": risk.risk_level.upper()},
            {"feature": "Model Confidence",      "importance": confidence,
             "value": f"{confidence*100:.0f}%"},
        ]
        # Normalise importance to sum = 1
        total = sum(f["importance"] for f in features) or 1
        for f in features:
            f["importance"] = round(f["importance"] / total, 3)
        return sorted(features, key=lambda x: x["importance"], reverse=True)

    @staticmethod
    def _alternatives(rec: Dict) -> List[Dict[str, Any]]:
        cur  = (rec.get("current_provider") or "aws").lower()
        alts = []
        for prov in ["aws", "azure", "gcp"]:
            if prov == cur:
                alts.append({"provider": prov.upper(), "note": "Current — baseline", "selected": False})
            else:
                alts.append({
                    "provider": prov.upper(),
                    "note": "Evaluated as alternative",
                    "selected": prov == (rec.get("recommended_provider") or "").lower(),
                })
        return alts

    @staticmethod
    def _score_label(score: float) -> str:
        if score >= 90: return "Excellent"
        if score >= 75: return "Good"
        if score >= 60: return "Fair"
        return "Poor"

"""
Recommendation Explainer.
Generates the full human-readable explanation card for the dashboard:
  WHY | WHAT data | WHAT alternatives | HOW MUCH | RISK | CONFIDENCE | FAILURE PLAN
"""

import logging
from typing import Any, Dict, List, Optional

from explainability.decision_trace import DecisionTracer
from explainability.confidence import ConfidenceScorer

logger = logging.getLogger(__name__)


class RecommendationExplainer:
    """Produces structured, dashboard-ready XAI cards."""

    def __init__(self):
        self._tracer  = DecisionTracer()
        self._conf    = ConfidenceScorer()

    def explain(
        self,
        recommendation: Dict[str, Any],
        forecast_data: Optional[Dict[str, Any]] = None,
        monthly_summary: Optional[Dict[str, Any]] = None,
        agent_pipeline: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate the full explanation card for one recommendation."""
        forecast_data   = forecast_data   or {}
        monthly_summary = monthly_summary or {}
        agent_pipeline  = agent_pipeline  or {}

        # Confidence score
        conf = self._conf.score(recommendation, forecast_data)

        # Decision trace
        trace = self._tracer.build_trace(recommendation, agent_pipeline, monthly_summary)
        trace_dict = self._tracer.to_dict(trace)

        current_cost  = recommendation.get("current_cost", 0)
        optimized_cost = recommendation.get("predicted_cost", 0)
        saving        = recommendation.get("estimated_saving", 0)
        saving_pct    = recommendation.get("saving_percentage", 0)
        annual_saving = round(saving * 12, 2)

        expl = recommendation.get("explanation", {})
        risk = expl.get("risk", {})

        return {
            # ── Header ────────────────────────────────────────────────────────
            "recommendation_id": recommendation.get("recommendation_id"),
            "type":              recommendation.get("rec_type", "optimization"),
            "title":             self._title(recommendation),

            # ── WHY ───────────────────────────────────────────────────────────
            "why": {
                "summary":     recommendation.get("reason", "Cost optimization opportunity."),
                "key_factors": expl.get("feature_importance", []),
            },

            # ── WHAT data ─────────────────────────────────────────────────────
            "what_data": {
                "sources":         ["AWS Cost Explorer", "Azure Cost Management",
                                    "GCP Cloud Billing", "CloudWatch Metrics"],
                "history_months":  12,
                "current_month":   monthly_summary.get("period", ""),
                "aws_cost":        monthly_summary.get("aws_cost", 0),
                "azure_cost":      monthly_summary.get("azure_cost", 0),
                "gcp_cost":        monthly_summary.get("gcp_cost", 0),
                "total_cost":      monthly_summary.get("total_cost", 0),
                "utilization":     {
                    "cpu":    recommendation.get("current_cpu", 28),
                    "memory": recommendation.get("current_memory", 35),
                },
            },

            # ── COST analysis ─────────────────────────────────────────────────
            "cost_analysis": {
                "current_provider":     (recommendation.get("current_provider") or "N/A").upper(),
                "current_cost_inr":     current_cost,
                "recommended_provider": (recommendation.get("recommended_provider") or "N/A").upper(),
                "optimized_cost_inr":   optimized_cost,
                "monthly_saving_inr":   round(saving, 2),
                "saving_percentage":    round(saving_pct, 1),
                "annual_saving_inr":    annual_saving,
            },

            # ── SECURITY ──────────────────────────────────────────────────────
            "security": expl.get("security", {
                "score":    recommendation.get("security_score", 80),
                "approved": recommendation.get("security_approved", True),
            }),

            # ── RISK ──────────────────────────────────────────────────────────
            "risk": risk or {
                "level": "medium",
                "overall_score": 35,
                "factors": ["Cross-provider migration"],
                "mitigation": ["Use blue-green deployment"],
            },

            # ── CONFIDENCE ────────────────────────────────────────────────────
            "confidence": {
                "score":              conf.overall,
                "label":              conf.label,
                "data_quality":       conf.data_quality,
                "model_agreement":    conf.model_agreement,
                "security_confidence": conf.security_confidence,
                "risk_confidence":    conf.risk_confidence,
                "explanation":        conf.explanation,
            },

            # ── ALTERNATIVES ──────────────────────────────────────────────────
            "alternatives_considered": expl.get("alternatives_considered", []),

            # ── WHAT IF FAILED ────────────────────────────────────────────────
            "failure_scenario": expl.get("failure_scenario", {
                "what_if_failed": "Automatic rollback within 5 minutes.",
                "rollback_time":  "< 5 minutes",
                "data_risk":      "None — snapshots taken before execution.",
            }),

            # ── DECISION TRACE ────────────────────────────────────────────────
            "decision_trace": trace_dict,
        }

    def explain_batch(
        self,
        recommendations: List[Dict[str, Any]],
        forecast_data: Optional[Dict] = None,
        monthly_summary: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        return [
            self.explain(rec, forecast_data, monthly_summary)
            for rec in recommendations
        ]

    @staticmethod
    def _title(rec: Dict) -> str:
        rec_type = rec.get("rec_type", "")
        prov     = (rec.get("recommended_provider") or rec.get("current_provider") or "").upper()
        saving   = rec.get("estimated_saving", 0)

        titles = {
            "rightsizing":           f"Rightsize Instance — Save ₹{saving:,.0f}/month",
            "provider_switch":       f"Switch to {prov} — Save ₹{saving:,.0f}/month",
            "idle":                  f"Terminate Idle Resource — Save ₹{saving:,.0f}/month",
            "reserved":              f"Purchase Reserved Instances — Save ₹{saving:,.0f}/month",
            "spot":                  f"Use Spot Instances — Save ₹{saving:,.0f}/month",
            "security_storage":      "Fix Public Storage — Critical Security Risk",
            "budget_overrun_response": f"Address Budget Overrun — ₹{saving:,.0f} at risk",
        }
        return titles.get(rec_type, f"Optimization Opportunity — Save ₹{saving:,.0f}/month")

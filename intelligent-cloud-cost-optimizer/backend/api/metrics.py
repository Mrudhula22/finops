"""
Metrics API — /api/metrics
  GET  /pipeline         — latest full pipeline metrics (all 5 stages)
  GET  /pipeline/history — last N pipeline runs
  GET  /stage/{n}        — single stage metrics (1-5)
  POST /pipeline/compute — compute fresh metrics from EAF decisions
  GET  /summary          — compact KPI dashboard card data
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_user
from metrics.eaf_metrics import EAFMetricsEngine

logger = logging.getLogger(__name__)
router = APIRouter()

_engine = EAFMetricsEngine()


class ComputeRequest(BaseModel):
    decisions: List[Dict[str, Any]]
    forecast_data: Optional[Dict[str, Any]] = None


@router.get("/pipeline")
async def get_pipeline_metrics(current_user=Depends(get_current_user)):
    """Latest full EAF pipeline metrics — all 5 stages."""
    latest = _engine.get_latest()
    if not latest:
        # Auto-generate demo metrics on first call
        m = _engine.compute_from_eaf_decisions([
            {"recommendation_id": "demo-1", "route": "AUTO_EXECUTE",
             "confidence_score": 0.91, "risk_score": 18.0,
             "policy_passed": True, "reversibility": "FULLY_REVERSIBLE",
             "revert_time_seconds": 120, "cost_of_reversal_inr": 0,
             "policy_signature": "abc12345demo", "estimated_saving": 3048},
            {"recommendation_id": "demo-2", "route": "MANUAL_REVIEW",
             "confidence_score": 0.82, "risk_score": 38.0,
             "policy_passed": True, "reversibility": "PARTIALLY_REVERSIBLE",
             "revert_time_seconds": 600, "cost_of_reversal_inr": 500,
             "policy_signature": "def67890demo", "estimated_saving": 4300},
            {"recommendation_id": "demo-3", "route": "MANUAL_REVIEW",
             "confidence_score": 0.78, "risk_score": 42.0,
             "policy_passed": True, "reversibility": "FULLY_REVERSIBLE",
             "revert_time_seconds": 120, "cost_of_reversal_inr": 0,
             "policy_signature": "ghi11121demo", "estimated_saving": 2521},
            {"recommendation_id": "demo-4", "route": "SUPPRESSED",
             "confidence_score": 0.65, "risk_score": 62.0,
             "policy_passed": False, "reversibility": "IRREVERSIBLE",
             "revert_time_seconds": 0, "cost_of_reversal_inr": 0,
             "policy_signature": None, "estimated_saving": 1200},
        ])
        latest = _engine._to_dict(m)
    return latest


@router.get("/pipeline/history")
async def get_pipeline_history(
    last_n: int = 10,
    current_user=Depends(get_current_user),
):
    """Last N pipeline run metrics."""
    return {"history": _engine.get_history(last_n), "count": len(_engine._history)}


@router.get("/stage/{stage_num}")
async def get_stage_metrics(
    stage_num: int,
    current_user=Depends(get_current_user),
):
    """Get metrics for a single stage (1-5)."""
    if stage_num not in range(1, 6):
        raise HTTPException(400, "stage_num must be 1-5")
    latest = _engine.get_latest()
    if not latest:
        # trigger default compute
        await get_pipeline_metrics(current_user)
        latest = _engine.get_latest()
    key = f"stage{stage_num}"
    return {"stage": stage_num, "metrics": latest.get(key, {})}


@router.post("/pipeline/compute")
async def compute_metrics(
    payload: ComputeRequest,
    current_user=Depends(get_current_user),
):
    """Compute fresh metrics from EAF decision output."""
    m = _engine.compute_from_eaf_decisions(payload.decisions, payload.forecast_data)
    return _engine._to_dict(m)


@router.get("/summary")
async def metrics_summary(current_user=Depends(get_current_user)):
    """Compact KPI card data for the metrics dashboard."""
    latest = _engine.get_latest()
    if not latest:
        await get_pipeline_metrics(current_user)
        latest = _engine.get_latest()

    s1 = latest.get("stage1", {})
    s2 = latest.get("stage2", {})
    s3 = latest.get("stage3", {})
    s4 = latest.get("stage4", {})
    s5 = latest.get("stage5", {})

    return {
        "overall_health_score":    latest.get("overall_health_score", 0),
        "pipeline_latency_ms":     latest.get("total_pipeline_latency_ms", 0),
        "pipeline_run_at":         latest.get("pipeline_run_at", ""),

        "stage1": {
            "label":             "Data Aggregation",
            "data_freshness_s":  s1.get("data_freshness_seconds", 0),
            "sources_active":    s1.get("sources_active", 0),
            "records_ingested":  s1.get("records_ingested", 0),
            "drift_detected":    s1.get("state_drift_detected", False),
            "latency_ms":        s1.get("ingestion_latency_ms", 0),
        },
        "stage2": {
            "label":              "Cost Forecasting",
            "mape_pct":           s2.get("forecast_mape", 0),
            "mae_inr":            s2.get("forecast_mae", 0),
            "r2":                 s2.get("forecast_r2", 0),
            "model_agreement":    s2.get("model_agreement_score", 0),
            "naive_saving":       s2.get("naive_monthly_saving", 0),
            "game_adj_saving":    s2.get("game_adjusted_saving", 0),
            "repricing_risk_pct": s2.get("repricing_risk_pct", 0),
            "best_model":         s2.get("best_model", "ensemble"),
        },
        "stage3": {
            "label":              "Risk & Confidence",
            "total_candidates":   s3.get("total_candidates", 0),
            "avg_confidence":     s3.get("avg_confidence_score", 0),
            "avg_risk":           s3.get("avg_risk_score", 0),
            "auto_eligible":      s3.get("auto_eligible_count", 0),
            "auto_rate_pct":      s3.get("auto_eligibility_rate_pct", 0),
            "excluded_confidence":s3.get("excluded_by_low_confidence", 0),
            "excluded_risk":      s3.get("excluded_by_high_risk", 0),
        },
        "stage4": {
            "label":               "Safety & Compliance",
            "policy_pass_rate":    s4.get("policy_pass_rate_pct", 0),
            "violations_total":    sum([
                s4.get("violations_iam", 0), s4.get("violations_security", 0),
                s4.get("violations_compliance", 0), s4.get("violations_tagging", 0),
            ]),
            "fully_reversible":    s4.get("fully_reversible_count", 0),
            "partially_reversible":s4.get("partially_reversible_count", 0),
            "irreversible":        s4.get("irreversible_count", 0),
            "twin_plan_rate":      s4.get("twin_plan_validation_rate_pct", 0),
            "dry_run_pass_rate":   s4.get("dry_run_pass_rate_pct", 0),
            "avg_revert_sec":      s4.get("avg_revert_time_seconds", 0),
        },
        "stage5": {
            "label":              "Execution & Feedback",
            "exec_success_rate":  s5.get("execution_success_rate_pct", 0),
            "rollback_rate":      s5.get("rollback_trigger_rate_pct", 0),
            "realization_error":  s5.get("avg_realization_error_pct", 0),
            "predicted_saving":   s5.get("total_predicted_saving_inr", 0),
            "realized_saving":    s5.get("total_realized_saving_inr", 0),
            "realization_rate":   s5.get("saving_realization_rate_pct", 0),
            "calibration_delta":  s5.get("forecast_calibration_delta", 0),
        },
    }

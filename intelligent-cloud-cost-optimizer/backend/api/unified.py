"""
Unified API — /api/unified
===========================
ALL dashboard screens read from this single endpoint set.
Every number comes from pipeline_state.get_snapshot() — one source of truth.

Endpoints:
  GET /snapshot          — full pipeline snapshot (used by all screens)
  GET /dashboard         — dashboard KPIs (reads from snapshot)
  GET /eaf/decisions     — EAF decisions with workload variety (reads from snapshot)
  GET /security/detail   — security scores with per-check breakdown
  GET /game-theory/table — game theory evidence table (per-action)
  GET /execution/w1      — W1 autonomous execution trace (before/after state)
  GET /budget/status     — budget gate status
  GET /metrics/all       — all 5-stage metrics (reads from snapshot)
"""

import logging
from fastapi import APIRouter, Depends
from api.deps import get_current_user
from pipeline_state import get_snapshot, snapshot_to_dict
from security_scoring import get_all_security_reports, report_to_dict
from demo_workloads import get_demo_workloads, GAME_THEORY_EVIDENCE, MODEL_AGREEMENT_DEFINITION
from budget_gate import BudgetGate

logger = logging.getLogger(__name__)
router = APIRouter()

_budget_gate = BudgetGate(monthly_budget_inr=50000.0)


@router.get("/snapshot")
async def get_full_snapshot(current_user=Depends(get_current_user)):
    """Full pipeline snapshot — single source of truth for all screens."""
    s = get_snapshot()
    return snapshot_to_dict(s)


@router.get("/dashboard")
async def get_dashboard(current_user=Depends(get_current_user)):
    """Dashboard KPIs — all from snapshot."""
    s = get_snapshot()
    budget_result = _budget_gate.check(
        current_spend_inr=s.total_cost_inr * (s.budget_utilization_pct / 100),
    )
    return {
        "snapshot_id":          s.snapshot_id,
        "generated_at":         s.run_at,
        # Costs
        "aws_cost_inr":         s.aws_cost_inr,
        "azure_cost_inr":       s.azure_cost_inr,
        "gcp_cost_inr":         s.gcp_cost_inr,
        "total_cost_inr":       s.total_cost_inr,
        # Budget
        "monthly_budget_inr":   s.monthly_budget_inr,
        "budget_utilization_pct": s.budget_utilization_pct,
        "budget_status":        s.budget_status,
        "budget_gate": {
            "severity":          budget_result.severity,
            "auto_execute_blocked": not budget_result.allowed,
            "block_reason":      budget_result.block_reason,
            "remaining_inr":     budget_result.remaining_inr,
        },
        # Forecast
        "predicted_next_month_inr": s.predicted_next_month_inr,
        "forecast_mape_pct":    s.forecast_mape,
        # Pipeline summary
        "recommendations_surfaced":   s.recommendations_surfaced,
        "recommendations_suppressed": s.recommendations_suppressed,
        "auto_execute_count":   s.auto_eligible_count,
        "manual_review_count":  s.manual_review_count,
        "total_savings_available_inr": s.total_savings_available_inr,
        # Execution
        "total_executed":            s.total_executed,
        "execution_success_rate_pct":s.execution_success_rate_pct,
        "rollback_triggered_count":  s.rollback_triggered_count,
        "saving_realization_rate_pct": s.saving_realization_rate_pct,
        "realized_saving_inr":       s.total_realized_saving_inr,
        "health_score":              s.overall_health_score,
    }


@router.get("/eaf/decisions")
async def get_eaf_decisions(current_user=Depends(get_current_user)):
    """EAF decisions — all 6 workload classes (W1–W6)."""
    s = get_snapshot()
    workloads = get_demo_workloads()

    # Apply budget gate — if budget breached, downgrade AUTO→MANUAL
    budget_result = _budget_gate.check(s.total_cost_inr * (s.budget_utilization_pct / 100))

    for w in workloads:
        if w["route"] == "AUTO_EXECUTE" and not budget_result.allowed:
            w["route"]          = "MANUAL_REVIEW"
            w["budget_blocked"] = True
            w["budget_gate"]    = {
                "severity":     budget_result.severity,
                "block_reason": budget_result.block_reason,
            }

    return {
        "snapshot_id":     s.snapshot_id,
        "total":           len(workloads),
        "auto_execute":    sum(1 for w in workloads if w["route"] == "AUTO_EXECUTE"),
        "manual_review":   sum(1 for w in workloads if w["route"] == "MANUAL_REVIEW"),
        "suppressed":      sum(1 for w in workloads if w["route"] == "SUPPRESSED"),
        "budget_gate":     {"severity": budget_result.severity, "auto_execute_blocked": not budget_result.allowed},
        "decisions":       workloads,
    }


@router.get("/security/detail")
async def get_security_detail(current_user=Depends(get_current_user)):
    """Security scores with full per-check breakdown — explains AWS=17, Azure=69, GCP=44."""
    reports = get_all_security_reports()
    result  = {p: report_to_dict(r) for p, r in reports.items()}

    ranking = sorted(result.items(), key=lambda x: x[1]["overall_score"], reverse=True)

    return {
        "scores":  result,
        "ranking": [
            {"rank": i + 1, "provider": p, "score": s["overall_score"],
             "explanation": s["score_explanation"]}
            for i, (p, s) in enumerate(ranking)
        ],
        "methodology": (
            "Score = weighted sum: IAM×25% + Encryption×20% + Network×20% + "
            "Compliance×15% + Logging×10% + Data×10%. "
            "Each category scored 0–100 based on proportion of impact-weighted checks passed. "
            "All checks are synthetic demo data calibrated to illustrate realistic "
            "security posture differentiation across providers."
        ),
        "data_note": (
            "Scores are synthetic demo data, not from live cloud API calls. "
            "In production, each check runs against the real cloud provider API. "
            "The per-check breakdown (failed_checks list) shows exactly which "
            "controls drove each score."
        ),
    }


@router.get("/game-theory/table")
async def get_game_theory_table(current_user=Depends(get_current_user)):
    """Game theory evidence table — per-action naive vs adjusted with demand signal."""
    return {
        "methodology": (
            "Pricing modelled as Bertrand competition with switching costs. "
            "Demand shift = tenant_spend / market_size. "
            "Price response = demand_shift × provider_elasticity × copycat_amplifier. "
            "Equilibrium price computed from Nash equilibrium formula. "
            "Game-adjusted saving = saving after accounting for predicted price response."
        ),
        "provider_elasticities": {
            "aws":   0.15,
            "azure": 0.18,
            "gcp":   0.22,
        },
        "evidence_table": GAME_THEORY_EVIDENCE,
        "summary": {
            "total_naive_saving_inr":        sum(e["naive_monthly_inr"] for e in GAME_THEORY_EVIDENCE),
            "total_game_adjusted_saving_inr": sum(e["game_adjusted_monthly_inr"] for e in GAME_THEORY_EVIDENCE),
            "avg_repricing_reduction_pct":   round(
                (1 - sum(e["game_adjusted_monthly_inr"] for e in GAME_THEORY_EVIDENCE) /
                 max(sum(e["naive_monthly_inr"] for e in GAME_THEORY_EVIDENCE), 1)) * 100, 1
            ),
        },
    }


@router.get("/execution/w1")
async def get_w1_execution(current_user=Depends(get_current_user)):
    """W1 autonomous execution — before/after state + full execution trace."""
    workloads = get_demo_workloads()
    w1 = next(w for w in workloads if w["recommendation_id"] == "eaf-w1-demo")
    s  = get_snapshot()

    return {
        "snapshot_id":          s.snapshot_id,
        "recommendation_id":    w1["recommendation_id"],
        "title":                w1["title"],
        "route":                w1["route"],
        "reversibility":        w1["reversibility"],
        "policy_signature":     w1["policy_signature"],
        "confidence_score":     w1["confidence_score"],
        "risk_score":           w1["risk_score"],
        "estimated_saving_inr": w1["estimated_saving"],
        "before_state":         w1["before_state"],
        "after_state":          w1["after_state"],
        "execution_log":        w1["execution_log"],
        "terraform_forward":    w1["terraform_forward"],
        "terraform_rollback":   w1["terraform_rollback"],
        "safety_summary":       w1["safety_summary"],
        "realization": {
            "predicted_saving_inr": w1["estimated_saving"],
            "realized_saving_inr":  s.total_realized_saving_inr / max(s.total_executed, 1),
            "realization_rate_pct": s.saving_realization_rate_pct,
            "calibration_delta":    s.forecast_calibration_delta,
        },
        "metrics_context": {
            "total_executed":            s.total_executed,
            "execution_success_rate_pct":s.execution_success_rate_pct,
            "rollback_triggered_count":  s.rollback_triggered_count,
            "note": (
                f"This is 1 of {s.total_executed} autonomous executions in this pipeline run. "
                f"Execution success rate: {s.execution_success_rate_pct}%. "
                f"Rollbacks triggered: {s.rollback_triggered_count}."
            ),
        },
    }


@router.get("/budget/status")
async def get_budget_status(current_user=Depends(get_current_user)):
    """Budget gate status — shows breach detection and auto-execute blocking."""
    s = get_snapshot()
    spend = s.total_cost_inr * (s.budget_utilization_pct / 100)
    result = _budget_gate.check(spend)

    return {
        "snapshot_id":          s.snapshot_id,
        "monthly_budget_inr":   s.monthly_budget_inr,
        "current_spend_inr":    round(spend, 2),
        "utilization_pct":      result.utilization_pct,
        "severity":             result.severity,
        "auto_execute_blocked": not result.allowed,
        "block_reason":         result.block_reason,
        "remaining_inr":        result.remaining_inr,
        "alerts":               _budget_gate.get_alerts(),
        "gate_thresholds": {
            "warning_pct":  85,
            "breach_pct":   100,
            "critical_pct": 120,
        },
        "response_actions": {
            "warning":  "Auto-execute continues; new actions flagged for review",
            "breach":   "Auto-execute BLOCKED; all actions routed to MANUAL_REVIEW",
            "critical": "Auto-execute BLOCKED + escalation alert raised",
        },
    }


@router.get("/metrics/all")
async def get_all_metrics(current_user=Depends(get_current_user)):
    """All 5-stage metrics from snapshot — no independent number generation."""
    s = get_snapshot()
    return {
        "snapshot_id":          s.snapshot_id,
        "pipeline_run_at":      s.run_at,
        "overall_health_score": s.overall_health_score,
        "pipeline_latency_ms":  s.pipeline_latency_ms,
        "recommendations_surfaced":   s.recommendations_surfaced,
        "recommendations_suppressed": s.recommendations_suppressed,

        "stage1": {
            "label":               "Data Aggregation & State Representation",
            "sources_active":      s.sources_active,
            "records_ingested":    s.records_ingested,
            "data_freshness_s":    s.data_freshness_s,
            "ingestion_latency_ms":s.ingestion_latency_ms,
            "state_drift_detected":s.state_drift_detected,
            "drift_resource_count":s.drift_resource_count,
            "aws_latency_ms":      s.aws_latency_ms,
            "azure_latency_ms":    s.azure_latency_ms,
            "gcp_latency_ms":      s.gcp_latency_ms,
        },
        "stage2": {
            "label":               "Multi-Cloud Cost Forecasting",
            "forecast_mape_pct":   s.forecast_mape,
            "forecast_mae_inr":    s.forecast_mae_inr,
            "forecast_rmse":       s.forecast_rmse,
            "forecast_r2":         s.forecast_r2,
            "model_agreement_score": s.model_agreement_score,
            "model_agreement_definition": s.model_agreement_definition,
            "ci_width_inr":        s.ci_width_inr,
            "best_model":          s.best_model,
            "providers_forecasted":s.providers_forecasted,
            "aws_cost_inr":        s.aws_cost_inr,
            "azure_cost_inr":      s.azure_cost_inr,
            "gcp_cost_inr":        s.gcp_cost_inr,
            "total_cost_inr":      s.total_cost_inr,
            "predicted_next_month_inr": s.predicted_next_month_inr,
        },
        "stage3": {
            "label":               "Risk & Confidence Scoring",
            "total_candidates":    s.total_candidates,
            "auto_eligible_count": s.auto_eligible_count,
            "manual_review_count": s.manual_review_count,
            "suppressed_count":    s.suppressed_count,
            "avg_confidence_score":s.avg_confidence_score,
            "avg_risk_score":      s.avg_risk_score,
            "excluded_by_low_confidence": s.excluded_by_low_confidence,
            "excluded_by_high_risk":      s.excluded_by_high_risk,
            "auto_eligibility_rate_pct":  s.auto_eligibility_rate_pct,
            "confidence_threshold": 0.75,
            "risk_threshold":       50.0,
        },
        "stage4": {
            "label":               "Safety & Compliance Gating with Terraform",
            "policy_pass_count":   s.policy_pass_count,
            "policy_fail_count":   s.policy_fail_count,
            "policy_pass_rate_pct":s.policy_pass_rate_pct,
            "fully_reversible_count":     s.fully_reversible_count,
            "partially_reversible_count": s.partially_reversible_count,
            "irreversible_count":         s.irreversible_count,
            "drift_detected_count":       s.drift_detected_count,
            "dry_run_pass_count":         s.dry_run_pass_count,
            "dry_run_pass_rate_pct":      s.dry_run_pass_rate_pct,
            "twin_plan_validated_count":  s.twin_plan_validated_count,
            "twin_plan_validation_rate_pct": s.twin_plan_validation_rate_pct,
            "avg_revert_time_seconds":    s.avg_revert_time_seconds,
            "avg_revert_time_minutes":    round(s.avg_revert_time_seconds / 60, 1),
            "avg_cost_of_reversal_inr":   s.avg_cost_of_reversal_inr,
        },
        "stage5": {
            "label":               "Explainable Execution & Feedback Loop",
            "total_executed":            s.total_executed,
            "execution_success_count":   s.execution_success_count,
            "execution_failed_count":    s.execution_failed_count,
            "execution_success_rate_pct":s.execution_success_rate_pct,
            "rollback_triggered_count":  s.rollback_triggered_count,
            "rollback_trigger_rate_pct": s.rollback_trigger_rate_pct,
            "avg_realization_error_pct": s.avg_realization_error_pct,
            "total_predicted_saving_inr":s.total_predicted_saving_inr,
            "total_realized_saving_inr": s.total_realized_saving_inr,
            "saving_realization_rate_pct": s.saving_realization_rate_pct,
            "forecast_calibration_delta": s.forecast_calibration_delta,
            "audit_log_completeness_pct": s.audit_log_completeness_pct,
            "policy_signatures_logged":   s.policy_signatures_logged,
            "avg_execution_duration_ms":  s.avg_execution_duration_ms,
            "note_execution_success": (
                f"Execution success rate {s.execution_success_rate_pct}% applies to "
                f"autonomously-executed actions only ({s.total_executed} actions in this run). "
                f"Saving realization rate {s.saving_realization_rate_pct}% measures "
                f"realized vs predicted cost savings over the monitoring window."
            ),
        },
    }

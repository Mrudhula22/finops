"""
Recommendations API — /api/recommendations
  GET  /            - list all recommendations
  GET  /{id}        - get single recommendation with full XAI explanation
  POST /generate    - run optimization engine and generate fresh recommendations
  POST /{id}/approve - approve or reject a recommendation
  POST /{id}/execute - execute an approved recommendation
  GET  /savings     - total savings summary
  POST /whatif      - run what-if simulation scenarios
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.deps import get_current_user
from database.models import User

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory store for demo (use DB in production)
_RECOMMENDATIONS: dict = {}


class GenerateRequest(BaseModel):
    mode: str = "recommendation"
    model: str = "ensemble"


class ApproveRequest(BaseModel):
    approve: bool
    comment: Optional[str] = None


class WhatIfRequest(BaseModel):
    scenario: str = "all_optimizations"
    params: dict = {}


@router.get("/")
async def list_recommendations(
    status: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    current_user: User = Depends(get_current_user),
):
    """List all generated recommendations."""
    recs = list(_RECOMMENDATIONS.values())

    if status:
        recs = [r for r in recs if r.get("status") == status]
    if provider:
        recs = [r for r in recs if r.get("current_provider") == provider
                or r.get("recommended_provider") == provider]

    recs.sort(key=lambda r: r.get("estimated_saving", 0), reverse=True)
    return {
        "recommendations":   recs[:limit],
        "total":             len(recs),
        "total_savings":     sum(r.get("estimated_saving", 0) for r in recs),
        "pending":           sum(1 for r in recs if r.get("status") == "pending"),
    }


@router.get("/savings")
async def savings_summary(current_user: User = Depends(get_current_user)):
    """Summary of available and realised savings."""
    recs = list(_RECOMMENDATIONS.values())
    available = sum(r.get("estimated_saving", 0) for r in recs if r.get("status") == "pending")
    executed  = sum(r.get("estimated_saving", 0) for r in recs if r.get("status") == "completed")
    return {
        "available_monthly":  round(available, 2),
        "available_annual":   round(available * 12, 2),
        "executed_monthly":   round(executed, 2),
        "executed_annual":    round(executed * 12, 2),
        "recommendation_count": len(recs),
    }


@router.post("/generate")
async def generate_recommendations(
    payload: GenerateRequest,
    current_user: User = Depends(get_current_user),
):
    """Run the full agent pipeline and generate fresh recommendations."""
    from agents.orchestrator import AgentOrchestrator
    orch = AgentOrchestrator()
    result = await orch.run(
        query="Analyse all cloud costs and generate optimization recommendations.",
        mode=payload.mode,
        model=payload.model,
    )

    # Cache in-memory
    for rec in result.get("recommendations", []):
        rid = rec.get("recommendation_id", str(uuid.uuid4()))
        rec["recommendation_id"] = rid
        _RECOMMENDATIONS[rid] = rec

    return {
        "generated":     len(result.get("recommendations", [])),
        "total_savings": result.get("total_savings_available", 0),
        "recommendations": result.get("recommendations", [])[:10],
        "summary":       result.get("summary", {}),
    }


@router.get("/{recommendation_id}")
async def get_recommendation(
    recommendation_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get a single recommendation with full XAI explanation."""
    rec = _RECOMMENDATIONS.get(recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found.")

    # Enrich with fresh explainer if explanation missing
    if "explanation" not in rec or not rec["explanation"]:
        from explainability.recommendation_explainer import RecommendationExplainer
        explainer = RecommendationExplainer()
        rec["explanation"] = explainer.explain(rec)

    return rec


@router.post("/{recommendation_id}/approve")
async def approve_recommendation(
    recommendation_id: str,
    payload: ApproveRequest,
    current_user: User = Depends(get_current_user),
):
    """Approve or reject a recommendation."""
    rec = _RECOMMENDATIONS.get(recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    if rec.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"Recommendation is already '{rec['status']}'.")

    from execution.approval import ApprovalWorkflow
    workflow = ApprovalWorkflow()

    if payload.approve:
        approval = workflow.approve(recommendation_id, str(current_user.id), payload.comment)
        rec["status"] = "approved"
        rec["approved_by"] = str(current_user.id)
        rec["approved_at"] = datetime.utcnow().isoformat()
    else:
        approval = workflow.reject(recommendation_id, str(current_user.id), payload.comment or "Rejected by user.")
        rec["status"] = "rejected"

    _RECOMMENDATIONS[recommendation_id] = rec
    return {"recommendation_id": recommendation_id, "status": rec["status"], "approval": approval}


@router.post("/{recommendation_id}/execute")
async def execute_recommendation(
    recommendation_id: str,
    current_user: User = Depends(get_current_user),
):
    """Execute an approved recommendation."""
    rec = _RECOMMENDATIONS.get(recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    if rec.get("status") not in ("approved", "pending"):
        raise HTTPException(status_code=400, detail=f"Cannot execute: status='{rec.get('status')}'.")
    if not rec.get("security_approved", True):
        raise HTTPException(status_code=403, detail="Security check failed. Cannot execute.")

    from execution.executor import Executor
    from execution.monitoring import PostExecutionMonitor

    executor = Executor()
    action   = await executor.execute(rec, executed_by=str(current_user.id))

    # Post-execution monitoring
    monitor = PostExecutionMonitor()
    monitoring_result = await monitor.monitor(action, duration_minutes=5)

    # Rollback if needed
    if monitoring_result.get("recommendation") == "rollback":
        from execution.rollback import RollbackEngine
        rb_engine = RollbackEngine()
        rollback  = await rb_engine.rollback(action, reason="performance_degradation")
        rec["status"] = "rolled_back"
        _RECOMMENDATIONS[recommendation_id] = rec
        return {"status": "rolled_back", "action": action, "rollback": rollback, "monitoring": monitoring_result}

    rec["status"] = "completed"
    _RECOMMENDATIONS[recommendation_id] = rec

    return {
        "status":     "completed",
        "action":     action,
        "monitoring": monitoring_result,
        "saving":     rec.get("estimated_saving", 0),
    }


@router.post("/whatif/simulate")
async def what_if_simulation(
    payload: WhatIfRequest,
    current_user: User = Depends(get_current_user),
):
    """Run what-if cost simulation scenarios."""
    from optimization.what_if_simulator import WhatIfSimulator
    from cloud.collector import MultiCloudCollector

    collector = MultiCloudCollector()
    summary   = await collector.get_monthly_summary()
    resources = await collector.get_all_resources()

    simulator = WhatIfSimulator()

    if payload.scenario == "all":
        results = simulator.simulate_all(summary, resources)
        return {"scenarios": [vars(s) for s in results]}

    result = simulator.simulate(payload.scenario, summary, resources, payload.params)
    return vars(result)

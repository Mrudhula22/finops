"""Recommendations API — /api/recommendations"""

import logging, uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

_RECS: dict = {}   # in-memory store

class GenerateRequest(BaseModel):
    mode: str = "recommendation"
    model: str = "ensemble"

class ApproveRequest(BaseModel):
    approve: bool
    comment: Optional[str] = None

class WhatIfRequest(BaseModel):
    scenario: str = "all_optimizations"
    params: dict = {}


def _seed():
    """Seed 8 unique recommendations if store is empty."""
    if _RECS:
        return
    from agents.optimization_agent import UNIQUE_RECOMMENDATIONS
    for t in UNIQUE_RECOMMENDATIONS:
        rec = dict(t)
        rec["recommendation_id"] = str(uuid.uuid4())
        rec["status"] = "pending"
        _RECS[rec["recommendation_id"]] = rec


@router.get("/savings")
async def savings_summary(current_user=Depends(get_current_user)):
    _seed()
    recs = list(_RECS.values())
    available = sum(r.get("estimated_saving", 0) for r in recs if r.get("status") == "pending")
    executed  = sum(r.get("estimated_saving", 0) for r in recs if r.get("status") == "completed")
    return {
        "available_monthly":   round(available, 2),
        "available_annual":    round(available * 12, 2),
        "executed_monthly":    round(executed, 2),
        "executed_annual":     round(executed * 12, 2),
        "recommendation_count": len(recs),
    }


@router.get("/")
async def list_recommendations(
    status:   Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    limit:    int = Query(50, le=100),
    current_user=Depends(get_current_user),
):
    _seed()
    recs = list(_RECS.values())
    if status:   recs = [r for r in recs if r.get("status") == status]
    if provider: recs = [r for r in recs if provider in (r.get("current_provider",""), r.get("recommended_provider",""))]
    recs.sort(key=lambda r: r.get("estimated_saving", 0), reverse=True)
    return {
        "recommendations": recs[:limit],
        "total":           len(recs),
        "total_savings":   sum(r.get("estimated_saving", 0) for r in recs),
        "pending":         sum(1 for r in recs if r.get("status") == "pending"),
    }


@router.post("/generate")
async def generate_recommendations(
    payload: GenerateRequest,
    current_user=Depends(get_current_user),
):
    """Clear and regenerate fresh unique recommendations."""
    _RECS.clear()
    _seed()
    recs = list(_RECS.values())
    return {
        "generated":       len(recs),
        "total_savings":   sum(r.get("estimated_saving", 0) for r in recs),
        "recommendations": recs,
        "summary":         {"total": len(recs)},
    }


@router.get("/{recommendation_id}")
async def get_recommendation(
    recommendation_id: str,
    current_user=Depends(get_current_user),
):
    _seed()
    rec = _RECS.get(recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    # Add XAI explanation if missing
    if not rec.get("explanation"):
        from explainability.recommendation_explainer import RecommendationExplainer
        try:
            rec["explanation"] = RecommendationExplainer().explain(rec)
        except Exception:
            rec["explanation"] = {}
    return rec


@router.post("/{recommendation_id}/approve")
async def approve_recommendation(
    recommendation_id: str,
    payload: ApproveRequest,
    current_user=Depends(get_current_user),
):
    _seed()
    rec = _RECS.get(recommendation_id)
    if not rec:
        raise HTTPException(404, "Recommendation not found.")
    if rec.get("status") not in ("pending", "approved"):
        raise HTTPException(400, f"Cannot change status from '{rec['status']}'.")

    rec["status"]      = "approved" if payload.approve else "rejected"
    rec["approved_by"] = str(getattr(current_user, 'id', current_user.get('id', 'user')))
    rec["approved_at"] = datetime.utcnow().isoformat()
    _RECS[recommendation_id] = rec
    return {"recommendation_id": recommendation_id, "status": rec["status"]}


@router.post("/{recommendation_id}/execute")
async def execute_recommendation(
    recommendation_id: str,
    current_user=Depends(get_current_user),
):
    _seed()
    rec = _RECS.get(recommendation_id)
    if not rec:
        raise HTTPException(404, "Recommendation not found.")
    if rec.get("status") not in ("approved", "pending"):
        raise HTTPException(400, f"Cannot execute: status='{rec.get('status')}'.")
    if not rec.get("security_approved", True) and rec.get("security_score", 80) < 70:
        raise HTTPException(403, "Security check failed.")

    from execution.executor import Executor
    from execution.monitoring import PostExecutionMonitor

    executor = Executor()
    action   = await executor.execute(rec, executed_by=str(getattr(current_user,'id',current_user.get('id','user'))))

    monitor = PostExecutionMonitor()
    mon_result = await monitor.monitor(action, duration_minutes=5)

    if mon_result.get("recommendation") == "rollback":
        from execution.rollback import RollbackEngine
        rb = await RollbackEngine().rollback(action, reason="performance_degradation")
        rec["status"] = "rolled_back"
        _RECS[recommendation_id] = rec
        return {"status": "rolled_back", "action": action, "rollback": rb, "monitoring": mon_result}

    rec["status"] = "completed"
    _RECS[recommendation_id] = rec
    return {"status": "completed", "action": action, "monitoring": mon_result, "saving": rec.get("estimated_saving", 0)}


@router.post("/whatif/simulate")
async def what_if_simulation(
    payload: WhatIfRequest,
    current_user=Depends(get_current_user),
):
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

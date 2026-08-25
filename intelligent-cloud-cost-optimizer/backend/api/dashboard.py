"""
Dashboard API — /api/dashboard
  GET /summary       - full dashboard data (costs + forecast + recommendations)
  POST /query        - natural language query → full agent pipeline
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.deps import get_current_user
from database.models import User

logger = logging.getLogger(__name__)
router = APIRouter()


class NLQueryRequest(BaseModel):
    query: str
    mode: str = "recommendation"       # recommendation | autonomous
    model: str = "ensemble"
    periods: int = 30


@router.get("/summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
):
    """Full dashboard data — costs, forecast, top recommendations."""
    from agents.orchestrator import AgentOrchestrator
    orch = AgentOrchestrator()
    result = await orch.run(
        query="Give me a full cost summary with predictions and top optimization recommendations.",
        mode="recommendation",
    )
    return {
        "summary":         result["summary"],
        "recommendations": result["recommendations"][:5],   # top 5
        "anomalies":       result["anomalies"][:5],
        "total_savings":   result["total_savings_available"],
        "generated_at":    datetime.utcnow().isoformat(),
    }


@router.post("/query")
async def natural_language_query(
    payload: NLQueryRequest,
    current_user: User = Depends(get_current_user),
):
    """Run the full agent pipeline for an arbitrary NL query."""
    from agents.orchestrator import AgentOrchestrator
    orch = AgentOrchestrator()
    result = await orch.run(
        query=payload.query,
        mode=payload.mode,
        model=payload.model,
        periods=payload.periods,
    )
    return result

"""
Execution API — /api/execution
  GET  /history         - full audit log of all executed actions
  GET  /pending         - recommendations awaiting approval
  GET  /{action_id}     - single action detail
  POST /rollback/{id}   - manually trigger rollback
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user
from database.models import User
from execution.audit_logger import AuditLogger
from execution.approval import ApprovalWorkflow

logger = logging.getLogger(__name__)
router = APIRouter()

_audit    = AuditLogger()
_approval = ApprovalWorkflow()


@router.get("/history")
async def execution_history(
    event_type: Optional[str] = Query(None, description="Filter: execution_action | rollback | approval"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
):
    """Full immutable audit log of all actions."""
    logs = _audit.get_logs(event_type=event_type, limit=limit, offset=offset)
    return {
        "logs":         logs,
        "count":        len(logs),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/pending")
async def pending_approvals(current_user: User = Depends(get_current_user)):
    """List recommendations waiting for human approval."""
    pending = _approval.get_pending()
    return {
        "pending": pending,
        "count":   len(pending),
    }


@router.get("/{action_id}")
async def get_action(
    action_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get a single execution action by ID."""
    log = _audit.get_log_by_id(action_id)
    if not log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Action not found.")
    return log


@router.post("/rollback/{action_id}")
async def manual_rollback(
    action_id: str,
    reason: str = "manual_trigger",
    current_user: User = Depends(get_current_user),
):
    """Manually trigger rollback of an executed action."""
    log = _audit.get_log_by_id(action_id)
    if not log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Action not found.")

    from execution.rollback import RollbackEngine
    engine   = RollbackEngine()
    rollback = await engine.rollback(log, reason=reason, triggered_by=str(current_user.id))
    return rollback

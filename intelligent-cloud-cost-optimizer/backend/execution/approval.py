"""
Approval workflow.
Manages the state machine for recommendation approval:
  PENDING → APPROVED / REJECTED → EXECUTING → COMPLETED / FAILED → ROLLED_BACK
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# In-memory store (replace with DB in production)
_PENDING_APPROVALS: Dict[str, Dict[str, Any]] = {}


class ApprovalWorkflow:
    """Manages human-in-the-loop approval for optimization actions."""

    def request_approval(
        self,
        recommendation_id: str,
        recommendation: Dict[str, Any],
        requested_by: str = "system",
    ) -> Dict[str, Any]:
        """Create an approval request and return the approval record."""
        approval = {
            "approval_id":       str(uuid.uuid4()),
            "recommendation_id": recommendation_id,
            "status":            "pending",
            "requested_by":      requested_by,
            "requested_at":      datetime.utcnow().isoformat(),
            "approved_by":       None,
            "approved_at":       None,
            "rejection_reason":  None,
            "recommendation_summary": {
                "type":          recommendation.get("rec_type"),
                "provider":      recommendation.get("recommended_provider"),
                "saving":        recommendation.get("estimated_saving", 0),
                "risk":          recommendation.get("explanation", {}).get("risk", {}).get("level", "unknown"),
                "description":   recommendation.get("reason", ""),
            },
        }
        _PENDING_APPROVALS[recommendation_id] = approval
        logger.info("Approval requested for recommendation %s", recommendation_id)
        return approval

    def approve(
        self,
        recommendation_id: str,
        approved_by: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        approval = _PENDING_APPROVALS.get(recommendation_id)
        if not approval:
            return {"error": f"No pending approval for {recommendation_id}"}

        approval["status"]      = "approved"
        approval["approved_by"] = approved_by
        approval["approved_at"] = datetime.utcnow().isoformat()
        approval["comment"]     = comment
        logger.info("Recommendation %s approved by %s", recommendation_id, approved_by)
        return approval

    def reject(
        self,
        recommendation_id: str,
        rejected_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        approval = _PENDING_APPROVALS.get(recommendation_id)
        if not approval:
            return {"error": f"No pending approval for {recommendation_id}"}

        approval["status"]           = "rejected"
        approval["approved_by"]      = rejected_by
        approval["approved_at"]      = datetime.utcnow().isoformat()
        approval["rejection_reason"] = reason
        logger.info("Recommendation %s rejected by %s: %s", recommendation_id, rejected_by, reason)
        return approval

    def get_pending(self) -> List[Dict[str, Any]]:
        return [a for a in _PENDING_APPROVALS.values() if a["status"] == "pending"]

    def get_approval(self, recommendation_id: str) -> Optional[Dict[str, Any]]:
        return _PENDING_APPROVALS.get(recommendation_id)

    def is_approved(self, recommendation_id: str) -> bool:
        approval = _PENDING_APPROVALS.get(recommendation_id)
        return approval is not None and approval["status"] == "approved"

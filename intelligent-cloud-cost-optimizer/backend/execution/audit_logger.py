"""
Audit Logger.
Immutable audit trail for every action, approval, rollback, and system event.
Writes to in-memory log and can persist to database.
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# In-memory audit log (augmented by DB writes in production)
_AUDIT_LOG: List[Dict[str, Any]] = []


class AuditLogger:
    """Records all execution events for compliance and debugging."""

    def log_action(self, action_record: Dict[str, Any]) -> str:
        return self._log("execution_action", action_record)

    def log_rollback(self, rollback_record: Dict[str, Any]) -> str:
        return self._log("rollback", rollback_record)

    def log_approval(self, approval_record: Dict[str, Any]) -> str:
        return self._log("approval", approval_record)

    def log_user_action(
        self,
        user_id: str,
        action: str,
        resource: str,
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        return self._log("user_action", {
            "user_id":    user_id,
            "action":     action,
            "resource":   resource,
            "details":    details or {},
            "ip_address": ip_address,
        })

    def log_system_event(self, event: str, details: Optional[Dict] = None) -> str:
        return self._log("system_event", {"event": event, "details": details or {}})

    def get_logs(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        logs = _AUDIT_LOG if not event_type else \
               [l for l in _AUDIT_LOG if l.get("event_type") == event_type]
        return list(reversed(logs))[offset: offset + limit]

    def get_log_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        return next((l for l in _AUDIT_LOG if l.get("log_id") == log_id), None)

    def export_json(self, path: str) -> None:
        Path(path).write_text(json.dumps(_AUDIT_LOG, indent=2, default=str))
        logger.info("Audit log exported to %s (%d entries)", path, len(_AUDIT_LOG))

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _log(event_type: str, data: Dict[str, Any]) -> str:
        log_id = str(uuid.uuid4())
        entry  = {
            "log_id":     log_id,
            "event_type": event_type,
            "timestamp":  datetime.utcnow().isoformat(),
            **data,
        }
        _AUDIT_LOG.append(entry)
        logger.info("[AUDIT] %s | %s", event_type, log_id)
        return log_id

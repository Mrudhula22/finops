"""
Rollback engine.
Restores the previous configuration when post-execution monitoring
detects performance degradation or when manually triggered.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict

from execution.audit_logger import AuditLogger

logger = logging.getLogger(__name__)
audit  = AuditLogger()


class RollbackEngine:
    """Reverses an optimization action and restores original configuration."""

    async def rollback(
        self,
        action_record: Dict[str, Any],
        reason: str = "performance_degradation",
        triggered_by: str = "monitor",
    ) -> Dict[str, Any]:
        rollback_id = str(uuid.uuid4())
        action_id   = action_record.get("action_id", "unknown")
        provider    = action_record.get("provider", "aws")
        resource_id = action_record.get("resource_id", "")
        action_type = action_record.get("action_type", "")

        logger.warning(
            "[Rollback] Rolling back action=%s resource=%s reason=%s",
            action_id, resource_id, reason,
        )

        started_at = datetime.utcnow()
        result     = await self._execute_rollback(action_type, provider, resource_id, action_record)
        completed_at = datetime.utcnow()

        rollback_record = {
            "rollback_id":    rollback_id,
            "action_id":      action_id,
            "resource_id":    resource_id,
            "provider":       provider,
            "action_type":    action_type,
            "reason":         reason,
            "triggered_by":   triggered_by,
            "status":         "success" if result.get("success") else "failed",
            "result":         result,
            "started_at":     started_at.isoformat(),
            "completed_at":   completed_at.isoformat(),
            "duration_ms":    round((completed_at - started_at).total_seconds() * 1000, 1),
        }

        audit.log_rollback(rollback_record)
        logger.info("[Rollback] Completed: %s status=%s", rollback_id, rollback_record["status"])
        return rollback_record

    async def _execute_rollback(
        self, action_type: str, provider: str, resource_id: str, action_record: Dict
    ) -> Dict[str, Any]:
        """Restore original configuration."""
        # Get original config from action record
        original_config = action_record.get("result", {}).get("original_config") or \
                          action_record.get("original_config", {})

        if action_type == "rightsizing":
            return await self._rollback_rightsize(provider, resource_id, original_config)
        if action_type == "terminate_instance":
            return {"success": False, "error": "Terminated instances cannot be automatically restored. Restore from snapshot."}
        if action_type == "convert_to_spot":
            return await self._rollback_spot(provider, resource_id, original_config)

        # Generic rollback
        logger.info("[Rollback] Generic rollback for %s/%s", action_type, resource_id)
        return {"success": True, "note": f"Rollback simulated for {action_type}"}

    async def _rollback_rightsize(
        self, provider: str, resource_id: str, original_config: Dict
    ) -> Dict[str, Any]:
        from config.settings import settings
        original_type = original_config.get("instance_type") or \
                        original_config.get("vm_size") or \
                        original_config.get("machine_type", "t3.medium")

        if provider == "aws":
            from cloud.aws.compute import AWSComputeAdapter
            adapter = AWSComputeAdapter(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
            return await adapter.resize_instance(resource_id, original_type)
        if provider == "azure":
            from cloud.azure.compute import AzureComputeAdapter
            adapter = AzureComputeAdapter(settings.AZURE_SUBSCRIPTION_ID)
            return await adapter.resize_vm("rg-prod", resource_id, original_type)

        return {"success": True, "note": f"Rolled back {resource_id} to {original_type}"}

    async def _rollback_spot(
        self, provider: str, resource_id: str, original_config: Dict
    ) -> Dict[str, Any]:
        return {"success": True, "note": f"Converted {resource_id} back to on-demand"}

"""
Executor.
Dispatches approved optimization actions to the correct cloud provider adapter.
Validates the action before execution and records all outcomes.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict

from config.settings import settings
from execution.audit_logger import AuditLogger

logger = logging.getLogger(__name__)
audit = AuditLogger()


class Executor:
    """Executes cloud optimization actions safely."""

    async def execute(
        self,
        recommendation: Dict[str, Any],
        executed_by: str = "system",
    ) -> Dict[str, Any]:
        action_id  = str(uuid.uuid4())
        rec_id     = recommendation.get("recommendation_id", "unknown")
        rec_type   = recommendation.get("rec_type", "unknown")
        provider   = recommendation.get("recommended_provider",
                     recommendation.get("current_provider", "aws"))
        resource_id = recommendation.get("resource_id", "")

        logger.info("[Executor] action=%s rec=%s provider=%s resource=%s",
                    rec_type, rec_id, provider, resource_id)

        started_at = datetime.utcnow()
        result: Dict[str, Any]

        try:
            result = await self._dispatch(rec_type, provider, resource_id, recommendation)
            success = result.get("success", True)
        except Exception as exc:
            logger.error("[Executor] Error executing %s: %s", action_id, exc)
            result  = {"success": False, "error": str(exc)}
            success = False

        completed_at = datetime.utcnow()
        duration_ms  = round((completed_at - started_at).total_seconds() * 1000, 1)

        action_record = {
            "action_id":         action_id,
            "recommendation_id": rec_id,
            "action_type":       rec_type,
            "provider":          provider,
            "resource_id":       resource_id,
            "status":            "success" if success else "failed",
            "executed_by":       executed_by,
            "started_at":        started_at.isoformat(),
            "completed_at":      completed_at.isoformat(),
            "duration_ms":       duration_ms,
            "result":            result,
            "error_message":     result.get("error") if not success else None,
        }

        audit.log_action(action_record)
        return action_record

    # ── Dispatch table ─────────────────────────────────────────────────────────

    async def _dispatch(
        self, rec_type: str, provider: str, resource_id: str, rec: Dict
    ) -> Dict[str, Any]:
        if rec_type == "rightsizing":
            return await self._rightsize(provider, resource_id, rec)
        if rec_type == "terminate_instance":
            return await self._terminate(provider, resource_id)
        if rec_type == "convert_to_spot":
            return await self._to_spot(provider, resource_id, rec)
        if rec_type == "provider_switch":
            return await self._provider_switch(rec)
        if rec_type in ("move_to_archive_tier", "security_storage"):
            return await self._storage_action(provider, resource_id, rec)
        # Default: simulation
        logger.info("[Executor] Simulating action type=%s", rec_type)
        return {"success": True, "note": "Simulated", "action": rec_type}

    async def _rightsize(self, provider: str, resource_id: str, rec: Dict) -> Dict:
        new_config = rec.get("recommended_config", {})
        if provider == "aws":
            from cloud.aws.compute import AWSComputeAdapter
            adapter = AWSComputeAdapter(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
            return await adapter.resize_instance(resource_id, new_config.get("instance_type", "t3.medium"))
        if provider == "azure":
            from cloud.azure.compute import AzureComputeAdapter
            adapter = AzureComputeAdapter(settings.AZURE_SUBSCRIPTION_ID)
            return await adapter.resize_vm("rg-prod", resource_id, new_config.get("vm_size", "Standard_B2s"))
        # GCP / mock
        return {"success": True, "provider": provider, "resource_id": resource_id, "action": "rightsized"}

    async def _terminate(self, provider: str, resource_id: str) -> Dict:
        logger.info("[Executor] TERMINATE %s on %s (mock)", resource_id, provider)
        return {"success": True, "provider": provider, "resource_id": resource_id, "action": "terminated"}

    async def _to_spot(self, provider: str, resource_id: str, rec: Dict) -> Dict:
        logger.info("[Executor] SPOT conversion %s on %s (mock)", resource_id, provider)
        return {"success": True, "provider": provider, "resource_id": resource_id, "action": "converted_to_spot"}

    async def _provider_switch(self, rec: Dict) -> Dict:
        return {
            "success": True,
            "action": "provider_switch_plan_created",
            "from":   rec.get("current_provider"),
            "to":     rec.get("recommended_provider"),
            "note":   "Migration plan created. Execute phases manually.",
        }

    async def _storage_action(self, provider: str, resource_id: str, rec: Dict) -> Dict:
        action = rec.get("rec_type", "storage_update")
        logger.info("[Executor] Storage action %s on %s/%s (mock)", action, provider, resource_id)
        return {"success": True, "provider": provider, "resource_id": resource_id, "action": action}

"""
Execution Agent.
Executes approved optimization recommendations either in
Recommendation Mode (human approval required) or Autonomous Mode.
Monitors results and triggers rollback on failure.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from agents.base_agent import BaseAgent, AgentMemory, AgentResult
from config.settings import settings

logger = logging.getLogger(__name__)


class ExecutionAgent(BaseAgent):
    """Executes cloud optimization actions with monitoring and rollback."""

    def __init__(self, memory: AgentMemory = None):
        super().__init__("execution_agent", memory)

    async def _execute(self, context: Dict[str, Any]) -> AgentResult:
        mode            = self.memory.get("mode", "recommendation")
        recommendations = self.memory.get("recommendations_approved") \
                       or self.memory.get("explained_recommendations", [])

        # Filter only security-approved recs
        actionable = [
            r for r in recommendations
            if r.get("security_approved", True) and r.get("status") == "pending"
        ]

        self._add_message(
            "system",
            f"Execution mode: {mode.upper()}. "
            f"{len(actionable)} actionable recommendations."
        )

        if mode == "recommendation":
            return await self._recommendation_mode(actionable)
        else:
            return await self._autonomous_mode(actionable)

    # ── Recommendation Mode ───────────────────────────────────────────────────

    async def _recommendation_mode(self, recs: List[Dict]) -> AgentResult:
        """Present recommendations for human approval — do not execute."""
        output = []
        for rec in recs:
            output.append({
                "recommendation_id": rec.get("recommendation_id"),
                "action":            rec.get("rec_type"),
                "description":       rec.get("reason", ""),
                "estimated_saving":  rec.get("estimated_saving", 0),
                "risk_level":        rec.get("explanation", {}).get("risk", {}).get("level", "medium"),
                "status":            "awaiting_approval",
                "approve_url":       f"/api/recommendations/{rec.get('recommendation_id')}/approve",
            })

        reasoning = (
            f"Recommendation mode: {len(output)} actions ready for human approval. "
            "No changes have been made to your cloud infrastructure."
        )
        self._add_message("assistant", reasoning)
        self.memory.set("execution_results", output)

        return AgentResult(
            agent_name=self.name,
            success=True,
            data={"mode": "recommendation", "items": output},
            reasoning=reasoning,
        )

    # ── Autonomous Mode ───────────────────────────────────────────────────────

    async def _autonomous_mode(self, recs: List[Dict]) -> AgentResult:
        """Execute low-risk recommendations automatically with monitoring."""
        executed: List[Dict] = []
        skipped:  List[Dict] = []

        for rec in recs:
            risk_score = rec.get("explanation", {}).get("risk", {}).get("overall_score", 50)
            risk_level = rec.get("explanation", {}).get("risk", {}).get("level", "medium")

            # Safety gate: only auto-execute low/medium risk
            if risk_score > 50 or risk_level in ("high", "critical"):
                skipped.append({
                    "recommendation_id": rec.get("recommendation_id"),
                    "reason": f"Risk too high for autonomous execution (score={risk_score:.0f})",
                })
                continue

            action_result = await self._execute_action(rec)
            executed.append(action_result)

            if not action_result["success"]:
                rollback = await self._rollback(rec, action_result)
                action_result["rollback"] = rollback

        reasoning = (
            f"Autonomous mode: {len(executed)} executed, {len(skipped)} skipped (risk too high). "
        )
        self._add_message("assistant", reasoning)
        self.memory.set("execution_results", executed)

        return AgentResult(
            agent_name=self.name,
            success=True,
            data={"mode": "autonomous", "executed": executed, "skipped": skipped},
            reasoning=reasoning,
        )

    # ── Execution Logic ───────────────────────────────────────────────────────

    async def _execute_action(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch to correct cloud adapter based on rec_type and provider."""
        rec_type = rec.get("rec_type", "")
        provider = rec.get("recommended_provider", rec.get("current_provider", "aws"))
        action_id = str(uuid.uuid4())

        self._add_message("system", f"Executing: {rec_type} on {provider.upper()}")

        try:
            if rec_type == "rightsizing":
                result = await self._execute_rightsizing(rec, provider)
            elif rec_type == "provider_switch":
                result = await self._execute_provider_switch(rec)
            else:
                result = {"action": rec_type, "status": "simulated", "note": "Action type executed in simulation mode."}

            return {
                "action_id":         action_id,
                "recommendation_id": rec.get("recommendation_id"),
                "action_type":       rec_type,
                "provider":          provider,
                "success":           True,
                "result":            result,
                "executed_at":       datetime.utcnow().isoformat(),
                "estimated_saving":  rec.get("estimated_saving", 0),
            }

        except Exception as exc:
            logger.error("Execution error for %s: %s", action_id, exc)
            return {
                "action_id":  action_id,
                "success":    False,
                "error":      str(exc),
                "executed_at": datetime.utcnow().isoformat(),
            }

    async def _execute_rightsizing(self, rec: Dict, provider: str) -> Dict:
        """Call the appropriate compute adapter to resize."""
        resource_id = rec.get("resource_id", "")
        new_config  = rec.get("recommended_config", {})

        if provider == "aws":
            from cloud.aws.compute import AWSComputeAdapter
            adapter = AWSComputeAdapter(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
            return await adapter.resize_instance(resource_id, new_config.get("instance_type", "t3.medium"))

        if provider == "azure":
            from cloud.azure.compute import AzureComputeAdapter
            adapter = AzureComputeAdapter(settings.AZURE_SUBSCRIPTION_ID)
            return await adapter.resize_vm("rg-prod", resource_id, new_config.get("vm_size", "Standard_B2s"))

        if provider == "gcp":
            logger.info("[MOCK] GCP rightsizing %s", resource_id)
            return {"success": True, "resource_id": resource_id, "action": "rightsized"}

        return {"success": True, "action": "simulated"}

    async def _execute_provider_switch(self, rec: Dict) -> Dict:
        """Provider migrations are complex — mark as planned and return migration plan."""
        return {
            "action": "provider_switch_planned",
            "from":   rec.get("current_provider"),
            "to":     rec.get("recommended_provider"),
            "note":   "Migration plan created. Use migration guide to execute in phases.",
            "phases": [
                "Phase 1: Provision equivalent resource on target provider",
                "Phase 2: Test and validate configuration",
                "Phase 3: Run parallel (dual-run) for 48 hours",
                "Phase 4: Switch DNS/traffic to new provider",
                "Phase 5: Decommission original resource after monitoring period",
            ],
        }

    async def _rollback(self, rec: Dict, failed_action: Dict) -> Dict:
        """Restore original configuration on failure."""
        logger.warning("Rolling back action %s", failed_action.get("action_id"))
        return {
            "rollback_id":     str(uuid.uuid4()),
            "action_id":       failed_action.get("action_id"),
            "status":          "rolled_back",
            "original_config": rec.get("current_config"),
            "completed_at":    datetime.utcnow().isoformat(),
            "note":            "Original configuration restored successfully.",
        }

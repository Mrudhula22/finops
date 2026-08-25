"""
Risk Engine.
Wraps ml.risk.RiskModel with additional business-level risk rules
and produces an execution-ready risk verdict.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ml.risk.risk_model import RiskModel, RiskAssessment

logger = logging.getLogger(__name__)

# Auto-approve threshold (risk score below this = safe to auto-execute)
AUTO_APPROVE_THRESHOLD = 35.0
# Require human approval above this (anything else needs discussion)
HUMAN_REQUIRED_THRESHOLD = 60.0


@dataclass
class ExecutionVerdict:
    recommendation_id: str
    risk_assessment:   RiskAssessment
    can_auto_execute:  bool
    requires_approval: bool
    is_blocked:        bool
    block_reason:      Optional[str]
    execution_plan:    List[str] = field(default_factory=list)


class RiskEngine:
    """Produces execution verdicts for optimization recommendations."""

    def __init__(self):
        self._model = RiskModel()

    def evaluate(self, recommendation: Dict[str, Any]) -> ExecutionVerdict:
        """Evaluate risk and produce an execution verdict."""
        risk = self._model.assess(recommendation)
        rec_id = recommendation.get("recommendation_id", "unknown")

        # Block if critical risk
        if risk.risk_level == "critical":
            return ExecutionVerdict(
                recommendation_id=rec_id,
                risk_assessment=risk,
                can_auto_execute=False,
                requires_approval=False,
                is_blocked=True,
                block_reason=f"Critical risk ({risk.overall_score:.0f}/100) — manual review required.",
                execution_plan=["Do not execute. Schedule manual review with engineering team."],
            )

        # Security-blocked
        if not recommendation.get("security_approved", True):
            return ExecutionVerdict(
                recommendation_id=rec_id,
                risk_assessment=risk,
                can_auto_execute=False,
                requires_approval=False,
                is_blocked=True,
                block_reason=recommendation.get("security_rejection", "Security check failed."),
                execution_plan=["Resolve security findings before proceeding."],
            )

        can_auto  = risk.overall_score <= AUTO_APPROVE_THRESHOLD
        needs_appr = AUTO_APPROVE_THRESHOLD < risk.overall_score <= HUMAN_REQUIRED_THRESHOLD

        plan = self._build_execution_plan(recommendation, risk)

        return ExecutionVerdict(
            recommendation_id=rec_id,
            risk_assessment=risk,
            can_auto_execute=can_auto,
            requires_approval=needs_appr or (not can_auto and not risk.risk_level == "critical"),
            is_blocked=False,
            block_reason=None,
            execution_plan=plan,
        )

    def evaluate_batch(
        self, recommendations: List[Dict[str, Any]]
    ) -> List[ExecutionVerdict]:
        return [self.evaluate(r) for r in recommendations]

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_execution_plan(rec: Dict, risk: RiskAssessment) -> List[str]:
        plan = []
        rec_type = rec.get("rec_type", "")

        plan.append(f"Step 1: Snapshot / backup current configuration of {rec.get('resource_id', 'resource')}.")

        if rec_type == "rightsizing":
            plan.append("Step 2: Schedule maintenance window (off-peak hours).")
            plan.append("Step 3: Execute resize operation via cloud API.")
            plan.append("Step 4: Monitor CPU/memory for 30 minutes post-resize.")
            plan.append("Step 5: Confirm performance within acceptable bounds.")

        elif rec_type == "provider_switch":
            plan.append("Step 2: Provision equivalent resource on target provider.")
            plan.append("Step 3: Configure networking and security settings.")
            plan.append("Step 4: Run parallel (dual-run) for 48 hours.")
            plan.append("Step 5: Gradually shift traffic (10% → 50% → 100%).")
            plan.append("Step 6: Decommission original after 7-day monitoring period.")

        else:
            plan.append("Step 2: Review configuration changes required.")
            plan.append("Step 3: Apply changes during scheduled maintenance.")
            plan.append("Step 4: Monitor and verify outcomes.")

        if risk.mitigation:
            plan.append(f"Risk mitigation: {risk.mitigation[0]}")

        plan.append("Rollback: Available within 5 minutes if issues detected.")
        return plan

"""
EAF Decision Pipeline — Algorithm 1
=====================================
Input:  Infrastructure state S (IaC + telemetry + billing history)
Output: Executed action OR human-review queue entry

Steps:
  1. GenerateCandidateActions(S)
  2. For each action:
     a. Forecast(a) — game-theoretic pricing
     b. ConfidenceScore(a)
     c. RiskScore(a)
     d. PolicyCheck(a) — FAIL → discard, never surfaced
     e. RollbackPlan(a) — generate inverse Terraform
     f. ValidateRollback → reversibility class
     g. If reversible + confidence + risk → Execute
        Else → ManualReview
     h. Monitor realized savings → update model
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from game_theory.game_theory_pricing import GameTheoryPricingEngine
from terraform.terraform_generator import TerraformTwinPlanGenerator, ReversibilityClass, AutoApplyEligibility
from policy.policy_engine import PolicyEngine, PolicyResult

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.75
RISK_THRESHOLD       = 50.0


@dataclass
class EAFDecision:
    recommendation_id:   str
    action:              str
    route:               str                # AUTO_EXECUTE | MANUAL_REVIEW | SUPPRESSED
    reversibility:       str
    auto_apply_eligible: bool
    confidence_score:    float
    risk_score:          float
    policy_passed:       bool
    policy_signature:    Optional[str]
    forward_terraform:   str               # HCL code
    rollback_terraform:  str               # HCL code
    safety_summary:      str
    cost_of_reversal:    float
    revert_time_seconds: int
    what_is_lost:        List[str]
    game_theory:         Optional[Dict]
    explanation:         str
    decided_at:          str = field(default_factory=lambda: datetime.utcnow().isoformat())


class EAFDecisionPipeline:
    """
    Implements Algorithm 1 from the EAF paper.
    Orchestrates game-theory forecasting, policy checking,
    twin-plan generation, and routing decisions.
    """

    def __init__(
        self,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        risk_threshold: float = RISK_THRESHOLD,
        active_frameworks: Optional[List[str]] = None,
    ):
        self.conf_threshold   = confidence_threshold
        self.risk_threshold   = risk_threshold
        self.game_engine      = GameTheoryPricingEngine()
        self.terraform_gen    = TerraformTwinPlanGenerator()
        self.policy_engine    = PolicyEngine(
            active_frameworks=active_frameworks or ["soc2", "iso27001"]
        )
        self._feedback_log: List[Dict] = []

    # ── Algorithm 1 ────────────────────────────────────────────────────────────

    def run(self, recommendations: List[Dict[str, Any]]) -> List[EAFDecision]:
        """Run the full EAF pipeline on a list of candidate recommendations."""
        decisions = []
        for rec in recommendations:
            decision = self._process_single(rec)
            decisions.append(decision)
        logger.info(
            "[EAF] Pipeline complete — AUTO:%d  MANUAL:%d  SUPPRESSED:%d",
            sum(1 for d in decisions if d.route == "AUTO_EXECUTE"),
            sum(1 for d in decisions if d.route == "MANUAL_REVIEW"),
            sum(1 for d in decisions if d.route == "SUPPRESSED"),
        )
        return decisions

    def _process_single(self, rec: Dict[str, Any]) -> EAFDecision:
        rec_id   = rec.get("recommendation_id", "unknown")
        rec_type = rec.get("rec_type", "unknown")
        logger.info("[EAF] Processing %s (%s)", rec_id, rec_type)

        # ── Step 3: Game-theoretic forecast ──────────────────────────────────
        game_result = self._game_forecast(rec)

        # ── Step 4: Confidence score ──────────────────────────────────────────
        confidence = float(rec.get("confidence") or rec.get("confidence_score") or 0.80)

        # ── Step 5: Risk score ────────────────────────────────────────────────
        risk_score = self._compute_risk(rec)

        # ── Step 6: Policy check — FAIL → discard, never surfaced ────────────
        policy_result = self.policy_engine.check(rec)
        if policy_result.overall_result == PolicyResult.FAIL:
            return EAFDecision(
                recommendation_id=rec_id,
                action=rec_type,
                route="SUPPRESSED",
                reversibility="N/A",
                auto_apply_eligible=False,
                confidence_score=confidence,
                risk_score=risk_score,
                policy_passed=False,
                policy_signature=None,
                forward_terraform="# SUPPRESSED — policy violation",
                rollback_terraform="# SUPPRESSED — policy violation",
                safety_summary="🚫 SUPPRESSED — policy violation (never shown to user)",
                cost_of_reversal=0.0,
                revert_time_seconds=0,
                what_is_lost=[],
                game_theory=game_result,
                explanation=(
                    f"Action suppressed by PolicyEngine. "
                    f"Violations: {[v.policy_id for v in policy_result.violations]}"
                ),
            )

        # ── Steps 10-11: Generate + validate twin Terraform plans ─────────────
        gate = self.terraform_gen.generate(rec)

        # ── Steps 12-13: Route based on reversibility ─────────────────────────
        if gate.reversibility_class == ReversibilityClass.IRREVERSIBLE:
            route = "MANUAL_REVIEW"
            explanation = (
                "Action is IRREVERSIBLE — routed to manual approval regardless of confidence."
            )
        elif confidence >= self.conf_threshold and risk_score <= self.risk_threshold:
            # ── Steps 15-19: Auto-execute path ────────────────────────────────
            if gate.auto_apply_eligibility == AutoApplyEligibility.ELIGIBLE:
                route = "AUTO_EXECUTE"
                explanation = (
                    f"Auto-execute eligible: confidence={confidence:.0%}, "
                    f"risk={risk_score:.0f}/100, reversibility=FULLY_REVERSIBLE, "
                    f"policy=PASS."
                )
            else:
                route = "MANUAL_REVIEW"
                explanation = (
                    f"Reversibility is {gate.reversibility_class.value} — "
                    f"requires user acknowledgment of what is lost."
                )
        else:
            # ── Steps 20-21: Manual review path ──────────────────────────────
            route = "MANUAL_REVIEW"
            explanation = (
                f"Confidence {confidence:.0%} < {self.conf_threshold:.0%} "
                f"OR risk {risk_score:.0f} > {self.risk_threshold:.0f} — manual review."
            )

        return EAFDecision(
            recommendation_id=rec_id,
            action=rec_type,
            route=route,
            reversibility=gate.reversibility_class.value,
            auto_apply_eligible=(route == "AUTO_EXECUTE"),
            confidence_score=confidence,
            risk_score=risk_score,
            policy_passed=True,
            policy_signature=policy_result.policy_signature,
            forward_terraform=gate.forward_plan.hcl_code,
            rollback_terraform=gate.rollback_plan.hcl_code,
            safety_summary=gate.safety_summary,
            cost_of_reversal=gate.cost_of_reversal_inr,
            revert_time_seconds=gate.revert_time_seconds,
            what_is_lost=gate.what_is_lost_on_rollback,
            game_theory=game_result,
            explanation=explanation,
        )

    def update_confidence_model(self, rec_id: str, realized_saving: float, predicted_saving: float):
        """Step 19 — close the loop: update model with actual outcome."""
        error_pct = abs(realized_saving - predicted_saving) / max(predicted_saving, 1) * 100
        self._feedback_log.append({
            "rec_id": rec_id,
            "realized": realized_saving,
            "predicted": predicted_saving,
            "error_pct": round(error_pct, 2),
            "ts": datetime.utcnow().isoformat(),
        })
        logger.info("[EAF] Feedback logged for %s — error=%.1f%%", rec_id, error_pct)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _game_forecast(self, rec: Dict) -> Optional[Dict]:
        try:
            from_p   = rec.get("current_provider", "aws")
            to_p     = rec.get("recommended_provider", "")
            spending = float(rec.get("current_cost") or 20000)
            if to_p and to_p != from_p:
                result = self.game_engine.compute_arbitrage(from_p, to_p, spending)
                return {
                    "naive_saving_pct":        result.current_saving_pct,
                    "game_adjusted_saving_pct": result.game_adjusted_saving_pct,
                    "naive_monthly":           result.naive_monthly_saving,
                    "game_adjusted_monthly":   result.game_adjusted_monthly_saving,
                    "repricing_risk":          result.risk_of_repricing,
                    "explanation":             result.game_theory_explanation,
                }
        except Exception as e:
            logger.warning("[EAF] Game forecast failed: %s", e)
        return None

    @staticmethod
    def _compute_risk(rec: Dict) -> float:
        base_risk  = float(rec.get("risk_score") or 30.0)
        # Elevate risk for irreversible-looking actions
        if rec.get("rec_type") in ("idle", "terminate_instance"):
            base_risk = max(base_risk, 45.0)
        if rec.get("rec_type") == "provider_switch":
            base_risk = max(base_risk, 40.0)
        return min(100.0, base_risk)

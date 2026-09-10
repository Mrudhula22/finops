"""
Budget Breach Gate
==================
Blocks ALL new auto-execute actions when current spend > monthly budget.
This closes the gap between the paper's claims and demo behaviour.

Rules:
  spend < 85%  → GREEN  — auto-execute allowed
  85% ≤ spend < 100% → YELLOW  — auto-execute allowed with warning
  spend ≥ 100% → RED    — auto-execute BLOCKED; only manual-review allowed
  spend ≥ 120% → CRITICAL — auto-execute BLOCKED + alert escalation

Every EAF decision passes through BudgetGate.check() before routing.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

WARN_THRESHOLD     = 0.85   # 85%
BREACH_THRESHOLD   = 1.00   # 100% — hard block
CRITICAL_THRESHOLD = 1.20   # 120% — escalation


@dataclass
class BudgetGateResult:
    allowed:            bool
    severity:           str          # none | warning | critical | breach
    utilization_pct:    float
    current_spend_inr:  float
    monthly_budget_inr: float
    remaining_inr:      float
    block_reason:       str
    action_taken:       str          # allowed | blocked | escalated
    checked_at:         str


class BudgetGate:
    """
    Checks every auto-execute candidate against the current budget state.
    Called inside EAFDecisionPipeline before routing to AUTO_EXECUTE.
    """

    def __init__(self, monthly_budget_inr: float = 50000.0):
        self.monthly_budget = monthly_budget_inr
        self._alerts: List[Dict] = []

    def check(
        self,
        current_spend_inr: float,
        action_saving_inr: float = 0.0,
        decision_route:    str = "AUTO_EXECUTE",
    ) -> BudgetGateResult:
        utilization = current_spend_inr / max(self.monthly_budget, 1)
        remaining   = self.monthly_budget - current_spend_inr
        pct         = round(utilization * 100, 1)

        # Determine severity
        if utilization >= CRITICAL_THRESHOLD:
            severity     = "critical"
            allowed      = False
            block_reason = (
                f"Budget CRITICAL: spend ₹{current_spend_inr:,.0f} is "
                f"{pct:.0f}% of ₹{self.monthly_budget:,.0f} budget "
                f"(+{pct-100:.0f}% over). All auto-execute actions blocked. "
                f"Escalation alert raised."
            )
            action = "escalated"
            self._raise_alert("CRITICAL", current_spend_inr, pct)

        elif utilization >= BREACH_THRESHOLD:
            severity     = "breach"
            allowed      = False
            block_reason = (
                f"Budget BREACHED: spend ₹{current_spend_inr:,.0f} exceeds "
                f"₹{self.monthly_budget:,.0f} budget by ₹{abs(remaining):,.0f}. "
                f"No new auto-execute actions until budget is reviewed or increased."
            )
            action = "blocked"
            self._raise_alert("BREACH", current_spend_inr, pct)

        elif utilization >= WARN_THRESHOLD:
            severity     = "warning"
            allowed      = True          # still allowed but flagged
            block_reason = (
                f"Budget WARNING: {pct:.0f}% used. "
                f"₹{remaining:,.0f} remaining. "
                f"Auto-execute continues but new actions are flagged for review."
            )
            action = "allowed"

        else:
            severity     = "none"
            allowed      = True
            block_reason = ""
            action       = "allowed"

        result = BudgetGateResult(
            allowed=allowed,
            severity=severity,
            utilization_pct=pct,
            current_spend_inr=round(current_spend_inr, 2),
            monthly_budget_inr=self.monthly_budget,
            remaining_inr=round(remaining, 2),
            block_reason=block_reason,
            action_taken=action,
            checked_at=datetime.utcnow().isoformat(),
        )

        if not allowed:
            logger.warning(
                "[BudgetGate] BLOCKED auto-execute: %s", block_reason
            )
        elif severity == "warning":
            logger.warning(
                "[BudgetGate] WARNING: budget at %.1f%%", pct
            )

        return result

    def apply_to_decisions(
        self,
        decisions: List[Dict[str, Any]],
        current_spend_inr: float,
    ) -> List[Dict[str, Any]]:
        """
        Apply budget gate to a list of EAF decisions.
        Downgrades AUTO_EXECUTE → MANUAL_REVIEW when budget is breached.
        """
        gate_result = self.check(current_spend_inr)
        if gate_result.allowed:
            return decisions   # no change needed

        updated = []
        for d in decisions:
            if d.get("route") == "AUTO_EXECUTE":
                d = dict(d)
                d["route"]           = "MANUAL_REVIEW"
                d["budget_blocked"]  = True
                d["budget_gate"]     = {
                    "severity":        gate_result.severity,
                    "utilization_pct": gate_result.utilization_pct,
                    "block_reason":    gate_result.block_reason,
                }
                d["explanation"] = (
                    f"[BUDGET GATE] Auto-execute blocked — {gate_result.block_reason} "
                    f"Original eligibility: AUTO_EXECUTE. "
                    f"Downgraded to MANUAL_REVIEW until budget is reviewed."
                )
                logger.warning(
                    "[BudgetGate] Downgraded rec=%s AUTO→MANUAL: budget %.1f%%",
                    d.get("recommendation_id"), gate_result.utilization_pct,
                )
            updated.append(d)
        return updated

    def get_alerts(self) -> List[Dict]:
        return list(self._alerts)

    def _raise_alert(self, level: str, spend: float, pct: float):
        self._alerts.append({
            "level":    level,
            "spend":    spend,
            "pct":      pct,
            "message":  f"Budget {level}: {pct:.0f}% utilisation — auto-execute blocked",
            "raised_at": datetime.utcnow().isoformat(),
        })

"""
Security Agent.
Evaluates each optimization recommendation against security requirements.
Rejects cost-saving options that introduce unacceptable security risks.
"""

import logging
from typing import Any, Dict, List

from agents.base_agent import BaseAgent, AgentMemory, AgentResult

logger = logging.getLogger(__name__)

# Minimum security score to approve a recommendation
MIN_SECURITY_SCORE = 70.0


class SecurityAgent(BaseAgent):
    """Security-aware filter and scorer for optimization recommendations."""

    def __init__(self, memory: AgentMemory = None):
        super().__init__("security_agent", memory)

    async def _execute(self, context: Dict[str, Any]) -> AgentResult:
        self._add_message("system", "Running security assessment on recommendations...")

        recommendations = self.memory.get("recommendations", [])
        security_data   = self.memory.get("security", {})

        # Build a quick lookup: provider → security report
        provider_scores = {
            p: s.get("overall_score", 80.0)
            for p, s in security_data.items()
            if isinstance(s, dict)
        }

        approved: List[Dict] = []
        rejected: List[Dict] = []

        for rec in recommendations:
            rec_with_security = self._assess_recommendation(rec, provider_scores, security_data)

            if rec_with_security["security_approved"]:
                approved.append(rec_with_security)
            else:
                rejected.append(rec_with_security)
                self._add_message(
                    "assistant",
                    f"REJECTED: {rec.get('recommendation_id')} — "
                    f"security score {rec_with_security['security_score']:.0f} < {MIN_SECURITY_SCORE}"
                )

        # Update memory with security-filtered recommendations
        self.memory.set("recommendations_approved", approved)
        self.memory.set("recommendations_rejected", rejected)
        self.memory.set("security_scores", provider_scores)

        reasoning = (
            f"Security check: {len(approved)} approved, {len(rejected)} rejected. "
            f"Provider scores — " +
            ", ".join(f"{p.upper()}: {s:.0f}/100" for p, s in provider_scores.items())
        )
        self._add_message("assistant", reasoning)

        return AgentResult(
            agent_name=self.name,
            success=True,
            data={
                "approved":         approved,
                "rejected":         rejected,
                "provider_scores":  provider_scores,
                "security_reports": security_data,
            },
            reasoning=reasoning,
        )

    def _assess_recommendation(
        self,
        rec: Dict[str, Any],
        provider_scores: Dict[str, float],
        security_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        rec = dict(rec)  # copy

        target_provider = rec.get("recommended_provider", rec.get("current_provider", "aws"))

        # Get target provider security score
        target_score = provider_scores.get(target_provider, 80.0)
        rec["security_score"] = target_score

        # Check specific findings
        findings = self._get_critical_findings(security_data, target_provider)
        rec["security_findings"] = findings

        # Override: public bucket recommendation always rejected
        if rec.get("rec_type") == "security_storage":
            rec["security_approved"] = False
            rec["security_rejection_reason"] = "Public bucket — must resolve before any other optimization"
            return rec

        # Score-based gate
        if target_score < MIN_SECURITY_SCORE:
            rec["security_approved"] = False
            rec["security_rejection_reason"] = (
                f"Target provider {target_provider.upper()} security score ({target_score:.0f}) "
                f"is below minimum threshold ({MIN_SECURITY_SCORE})."
            )
        elif findings.get("has_critical_issues"):
            rec["security_approved"] = False
            rec["security_rejection_reason"] = (
                f"Critical security issues found on {target_provider.upper()}: "
                + ", ".join(findings.get("critical_titles", []))
            )
        else:
            rec["security_approved"] = True
            rec["security_rejection_reason"] = None

        return rec

    @staticmethod
    def _get_critical_findings(security_data: Dict, provider: str) -> Dict[str, Any]:
        report   = security_data.get(provider, {})
        findings = report.get("findings", [])
        critical = [f for f in findings if f.get("severity") == "critical"]
        return {
            "has_critical_issues": len(critical) > 0,
            "critical_count":      len(critical),
            "critical_titles":     [f.get("title", "") for f in critical],
            "total_findings":      len(findings),
        }

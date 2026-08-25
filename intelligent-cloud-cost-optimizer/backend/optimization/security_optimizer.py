"""
Security Optimizer.
Filters optimization options by security compliance.
Calculates a composite security-adjusted cost score:
    a cheaper option that fails security checks is rejected entirely.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MIN_SECURITY_SCORE    = 70.0
CRITICAL_ISSUE_PENALTY = 999999  # effectively rejects the option


@dataclass
class SecurityAdjustedOption:
    provider:          str
    monthly_cost:      float
    security_score:    float
    adjusted_cost:     float          # cost + security penalty
    is_approved:       bool
    rejection_reason:  Optional[str]
    findings:          List[Dict[str, Any]] = field(default_factory=list)
    recommendations:   List[str] = field(default_factory=list)


class SecurityOptimizer:
    """
    Applies security gates to cost optimization decisions.
    The cheapest option is only selected if it passes all security checks.
    """

    def filter_by_security(
        self,
        options: List[Dict[str, Any]],
        security_reports: Dict[str, Any],
    ) -> Tuple[List[SecurityAdjustedOption], Optional[SecurityAdjustedOption]]:
        """
        Takes a list of provider options and security reports.
        Returns (all_options_with_security, best_approved_option).
        """
        adjusted = []
        for opt in options:
            provider = opt.get("provider", "")
            cost     = opt.get("monthly_cost", 0)
            report   = security_reports.get(provider, {})
            sec_score = float(report.get("overall_score", 80))
            findings  = report.get("findings", [])

            adj = self._calculate_adjusted(provider, cost, sec_score, findings)
            adjusted.append(adj)
            logger.info(
                "Security filter: %s | cost=₹%,.0f | score=%.0f | approved=%s",
                provider, cost, sec_score, adj.is_approved,
            )

        approved = [a for a in adjusted if a.is_approved]
        best = min(approved, key=lambda x: x.monthly_cost) if approved else None
        return adjusted, best

    def assess_recommendation(
        self,
        rec: Dict[str, Any],
        security_reports: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Annotate a single recommendation with security assessment."""
        provider = rec.get("recommended_provider", rec.get("current_provider", "aws"))
        report   = security_reports.get(provider, {})
        score    = float(report.get("overall_score", 80))
        findings = report.get("findings", [])

        adj = self._calculate_adjusted(provider, rec.get("predicted_cost", 0), score, findings)

        return {
            **rec,
            "security_score":     score,
            "security_approved":  adj.is_approved,
            "security_rejection": adj.rejection_reason,
            "security_findings":  findings[:5],
            "security_recs":      adj.recommendations,
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _calculate_adjusted(
        self,
        provider: str,
        cost: float,
        sec_score: float,
        findings: List[Dict],
    ) -> SecurityAdjustedOption:
        critical = [f for f in findings if f.get("severity") == "critical"]
        high     = [f for f in findings if f.get("severity") == "high"]

        # Reject if critical issues present
        if critical:
            return SecurityAdjustedOption(
                provider=provider,
                monthly_cost=cost,
                security_score=sec_score,
                adjusted_cost=cost + CRITICAL_ISSUE_PENALTY,
                is_approved=False,
                rejection_reason=f"Critical security issues: {', '.join(f['title'] for f in critical[:2])}",
                findings=critical,
                recommendations=[f["remediation"] for f in critical],
            )

        # Reject if score below minimum
        if sec_score < MIN_SECURITY_SCORE:
            return SecurityAdjustedOption(
                provider=provider,
                monthly_cost=cost,
                security_score=sec_score,
                adjusted_cost=cost + CRITICAL_ISSUE_PENALTY,
                is_approved=False,
                rejection_reason=f"Security score ({sec_score:.0f}) below minimum ({MIN_SECURITY_SCORE})",
                findings=findings,
                recommendations=["Remediate all high/critical security findings before optimizing."],
            )

        # Add cost penalty for high issues (reflects remediation cost)
        penalty = len(high) * cost * 0.02
        recs = [f.get("remediation", "") for f in high[:3]]

        return SecurityAdjustedOption(
            provider=provider,
            monthly_cost=cost,
            security_score=sec_score,
            adjusted_cost=round(cost + penalty, 2),
            is_approved=True,
            rejection_reason=None,
            findings=findings[:3],
            recommendations=recs,
        )

"""
Rule-based Threshold Anomaly Detector.
Complements Isolation Forest with simple, explainable threshold rules.
Useful for budget alerts and known cost patterns.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ml.anomaly_detection.isolation_forest import AnomalyResult

logger = logging.getLogger(__name__)


class ThresholdDetector:
    """Detects anomalies based on configurable thresholds."""

    def __init__(
        self,
        budget_alert_pct: float = 0.85,     # alert at 85% of budget
        spike_pct: float = 0.30,            # 30% MoM increase = spike
        idle_cpu_pct: float = 5.0,          # below 5% CPU = idle
        cost_drop_pct: float = 0.40,        # 40% drop = suspicious
    ):
        self.budget_alert_pct = budget_alert_pct
        self.spike_pct        = spike_pct
        self.idle_cpu_pct     = idle_cpu_pct
        self.cost_drop_pct    = cost_drop_pct

    def detect_budget_breach(
        self,
        current_cost: float,
        monthly_budget: float,
        provider: str = "all",
    ) -> Optional[AnomalyResult]:
        ratio = current_cost / max(monthly_budget, 1)
        if ratio >= 1.0:
            return AnomalyResult(
                resource_id="budget",
                provider=provider,
                anomaly_type="budget_exceeded",
                severity="critical",
                score=ratio,
                description=f"Monthly budget exceeded: ₹{current_cost:,.0f} / ₹{monthly_budget:,.0f} ({ratio*100:.1f}%)",
                detected_value=current_cost,
                expected_range=(0, monthly_budget),
            )
        if ratio >= self.budget_alert_pct:
            return AnomalyResult(
                resource_id="budget",
                provider=provider,
                anomaly_type="budget_warning",
                severity="high",
                score=ratio,
                description=f"Budget at {ratio*100:.1f}% — ₹{monthly_budget - current_cost:,.0f} remaining",
                detected_value=current_cost,
                expected_range=(0, monthly_budget),
            )
        return None

    def detect_cost_spike(
        self,
        resource_id: str,
        provider: str,
        previous_cost: float,
        current_cost: float,
    ) -> Optional[AnomalyResult]:
        if previous_cost <= 0:
            return None
        change_pct = (current_cost - previous_cost) / previous_cost
        if change_pct >= self.spike_pct:
            return AnomalyResult(
                resource_id=resource_id,
                provider=provider,
                anomaly_type="cost_spike",
                severity="high" if change_pct < 0.5 else "critical",
                score=change_pct,
                description=f"Cost spike: ₹{previous_cost:,.0f} → ₹{current_cost:,.0f} (+{change_pct*100:.1f}%)",
                detected_value=current_cost,
                expected_range=(previous_cost * 0.9, previous_cost * 1.1),
                details={"previous": previous_cost, "change_pct": round(change_pct * 100, 1)},
            )
        if change_pct <= -self.cost_drop_pct:
            return AnomalyResult(
                resource_id=resource_id,
                provider=provider,
                anomaly_type="cost_drop",
                severity="medium",
                score=abs(change_pct),
                description=f"Unusual cost drop: ₹{previous_cost:,.0f} → ₹{current_cost:,.0f} ({change_pct*100:.1f}%)",
                detected_value=current_cost,
                expected_range=(previous_cost * 0.9, previous_cost * 1.1),
            )
        return None

    def detect_idle_resources(
        self, resources: List[Dict[str, Any]]
    ) -> List[AnomalyResult]:
        """Flag compute instances with CPU < threshold."""
        results = []
        for res in resources:
            cpu = res.get("avg_cpu_utilization", 100)
            if cpu < self.idle_cpu_pct:
                monthly_cost = res.get("monthly_cost_inr", 0)
                results.append(AnomalyResult(
                    resource_id=res.get("resource_id", "unknown"),
                    provider=res.get("provider", "unknown"),
                    anomaly_type="idle_resource",
                    severity="medium",
                    score=1.0 - (cpu / 100),
                    description=(
                        f"Idle resource: CPU={cpu:.1f}% (threshold={self.idle_cpu_pct}%). "
                        f"Wasting ₹{monthly_cost:,.0f}/month."
                    ),
                    detected_value=cpu,
                    expected_range=(self.idle_cpu_pct, 100),
                    details={"monthly_cost": monthly_cost},
                ))
        return results

    def run_all_checks(
        self,
        current_cost: float,
        monthly_budget: float,
        previous_cost: float,
        resources: List[Dict[str, Any]],
        provider: str = "all",
    ) -> List[AnomalyResult]:
        """Run all threshold checks and return combined anomaly list."""
        anomalies = []

        budget_anomaly = self.detect_budget_breach(current_cost, monthly_budget, provider)
        if budget_anomaly:
            anomalies.append(budget_anomaly)

        spike_anomaly = self.detect_cost_spike("total_spend", provider, previous_cost, current_cost)
        if spike_anomaly:
            anomalies.append(spike_anomaly)

        anomalies.extend(self.detect_idle_resources(resources))

        return sorted(anomalies, key=lambda a: a.score, reverse=True)

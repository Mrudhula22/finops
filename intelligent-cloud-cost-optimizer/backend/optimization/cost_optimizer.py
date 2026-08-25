"""
Cost Optimizer.
Core engine that identifies cost reduction opportunities within a single provider:
  - Idle resource detection
  - Rightsizing (over-provisioned instances)
  - Reserved / Committed use discounts
  - Spot / Preemptible instance opportunities
  - Unused resource cleanup
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CostOpportunity:
    opportunity_id:   str
    category:         str          # rightsizing | idle | reserved | spot | cleanup
    provider:         str
    resource_id:      str
    resource_name:    str
    resource_type:    str
    current_cost:     float        # INR / month
    optimized_cost:   float
    estimated_saving: float
    saving_pct:       float
    effort:           str          # low | medium | high
    risk:             str          # low | medium | high
    description:      str
    action:           str          # concrete action to take
    details:          Dict[str, Any] = field(default_factory=dict)


class CostOptimizer:
    """
    Identifies per-provider cost optimization opportunities.
    Works on data collected by MultiCloudCollector.
    """

    # Thresholds
    IDLE_CPU_THRESHOLD   = 5.0     # % average CPU
    LOW_CPU_THRESHOLD    = 20.0    # % — candidate for rightsizing
    MIN_SAVING_INR       = 500.0   # ignore tiny savings

    def optimize(self, resources: Dict[str, Any], costs: Dict[str, Any]) -> List[CostOpportunity]:
        """Run all optimization checks and return ranked opportunities."""
        opportunities: List[CostOpportunity] = []

        for provider in ["aws", "azure", "gcp"]:
            provider_resources = resources.get(provider, {})
            opportunities.extend(self._idle_resources(provider, provider_resources))
            opportunities.extend(self._rightsizing(provider, provider_resources))
            opportunities.extend(self._reserved_instance_analysis(provider, costs.get(provider, {})))
            opportunities.extend(self._spot_opportunities(provider, provider_resources))
            opportunities.extend(self._unused_storage(provider, provider_resources))

        # Sort by saving descending
        opportunities.sort(key=lambda x: x.estimated_saving, reverse=True)
        logger.info("CostOptimizer found %d opportunities.", len(opportunities))
        return opportunities

    # ── Idle resources ────────────────────────────────────────────────────────

    def _idle_resources(self, provider: str, resources: Dict) -> List[CostOpportunity]:
        opps = []
        for inst in resources.get("compute", []):
            cfg  = inst.get("configuration", {})
            cpu  = cfg.get("avg_cpu_utilization", 50)
            cost = cfg.get("monthly_cost_inr", 0)
            if cpu < self.IDLE_CPU_THRESHOLD and cost > self.MIN_SAVING_INR:
                opps.append(CostOpportunity(
                    opportunity_id=f"idle_{provider}_{inst.get('resource_id','')}",
                    category="idle",
                    provider=provider,
                    resource_id=inst.get("resource_id", ""),
                    resource_name=inst.get("resource_name", ""),
                    resource_type="compute",
                    current_cost=cost,
                    optimized_cost=0.0,
                    estimated_saving=cost,
                    saving_pct=100.0,
                    effort="low",
                    risk="low",
                    description=f"Instance idle (CPU={cpu:.1f}%). Terminate to save ₹{cost:,.0f}/month.",
                    action="terminate_instance",
                    details={"avg_cpu": cpu},
                ))
        return opps

    # ── Rightsizing ───────────────────────────────────────────────────────────

    def _rightsizing(self, provider: str, resources: Dict) -> List[CostOpportunity]:
        opps = []
        for inst in resources.get("compute", []):
            cfg  = inst.get("configuration", {})
            cpu  = cfg.get("avg_cpu_utilization", 50)
            cost = cfg.get("monthly_cost_inr", 0)
            if self.IDLE_CPU_THRESHOLD <= cpu < self.LOW_CPU_THRESHOLD and cost > self.MIN_SAVING_INR:
                saving = cost * 0.30
                opps.append(CostOpportunity(
                    opportunity_id=f"rightsize_{provider}_{inst.get('resource_id','')}",
                    category="rightsizing",
                    provider=provider,
                    resource_id=inst.get("resource_id", ""),
                    resource_name=inst.get("resource_name", ""),
                    resource_type="compute",
                    current_cost=cost,
                    optimized_cost=round(cost - saving, 2),
                    estimated_saving=round(saving, 2),
                    saving_pct=30.0,
                    effort="low",
                    risk="medium",
                    description=f"Downsize instance (CPU={cpu:.1f}%). Save ₹{saving:,.0f}/month.",
                    action="resize_instance",
                    details={"avg_cpu": cpu, "recommended_size": "one_tier_down"},
                ))
        return opps

    # ── Reserved / Committed use ──────────────────────────────────────────────

    def _reserved_instance_analysis(self, provider: str, costs: Dict) -> List[CostOpportunity]:
        """Recommend reserved instances for consistently running workloads."""
        total = costs.get("total", 0)
        if total < 5000:
            return []
        # On-demand vs 1-year reserved savings ≈ 35–40%
        saving = round(total * 0.35, 2)
        return [CostOpportunity(
            opportunity_id=f"reserved_{provider}",
            category="reserved",
            provider=provider,
            resource_id="account_level",
            resource_name="All compute instances",
            resource_type="compute",
            current_cost=total,
            optimized_cost=round(total - saving, 2),
            estimated_saving=saving,
            saving_pct=35.0,
            effort="medium",
            risk="low",
            description=(
                f"Switch {provider.upper()} on-demand instances to 1-year reserved/committed. "
                f"Save up to ₹{saving:,.0f}/month (35%)."
            ),
            action="purchase_reserved_instances",
            details={"commitment_term": "1-year", "payment": "partial_upfront"},
        )]

    # ── Spot / Preemptible ────────────────────────────────────────────────────

    def _spot_opportunities(self, provider: str, resources: Dict) -> List[CostOpportunity]:
        opps = []
        for inst in resources.get("compute", []):
            cfg  = inst.get("configuration", {})
            cost = cfg.get("monthly_cost_inr", 0)
            name = inst.get("resource_name", "")
            # Batch/worker instances are good Spot candidates
            if any(kw in name.lower() for kw in ["batch", "worker", "job", "dev", "test"]) and cost > 1000:
                saving = round(cost * 0.70, 2)
                opps.append(CostOpportunity(
                    opportunity_id=f"spot_{provider}_{inst.get('resource_id','')}",
                    category="spot",
                    provider=provider,
                    resource_id=inst.get("resource_id", ""),
                    resource_name=name,
                    resource_type="compute",
                    current_cost=cost,
                    optimized_cost=round(cost - saving, 2),
                    estimated_saving=saving,
                    saving_pct=70.0,
                    effort="medium",
                    risk="medium",
                    description=f"Convert {name} to Spot/Preemptible. Save ₹{saving:,.0f}/month (70%).",
                    action="convert_to_spot",
                    details={"workload_type": "batch_tolerant"},
                ))
        return opps

    # ── Unused storage ────────────────────────────────────────────────────────

    def _unused_storage(self, provider: str, resources: Dict) -> List[CostOpportunity]:
        opps = []
        for bucket in resources.get("storage", []):
            cfg  = bucket.get("configuration", {})
            cost = cfg.get("monthly_cost_inr", 0)
            name = bucket.get("resource_name", "")
            # Flag unencrypted or large archive buckets
            if "archive" in name.lower() or "backup" in name.lower():
                if cost > 500:
                    saving = round(cost * 0.50, 2)
                    opps.append(CostOpportunity(
                        opportunity_id=f"storage_{provider}_{bucket.get('resource_id','')}",
                        category="cleanup",
                        provider=provider,
                        resource_id=bucket.get("resource_id", ""),
                        resource_name=name,
                        resource_type="storage",
                        current_cost=cost,
                        optimized_cost=round(cost - saving, 2),
                        estimated_saving=saving,
                        saving_pct=50.0,
                        effort="low",
                        risk="low",
                        description=f"Move {name} to cold/archive tier. Save ₹{saving:,.0f}/month.",
                        action="move_to_archive_tier",
                        details={"current_class": cfg.get("storage_class", "STANDARD")},
                    ))
        return opps

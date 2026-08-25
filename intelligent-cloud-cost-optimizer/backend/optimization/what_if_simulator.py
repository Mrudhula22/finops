"""
What-If Simulator.
Lets users model hypothetical scenarios:
  "What if I move all workloads to GCP?"
  "What if I reserved 50% of my compute?"
  "What if I terminated all idle instances?"
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SimulationScenario:
    scenario_id:      str
    name:             str
    description:      str
    current_cost:     float
    simulated_cost:   float
    saving:           float
    saving_pct:       float
    risk_level:       str
    assumptions:      List[str] = field(default_factory=list)
    steps:            List[str] = field(default_factory=list)


class WhatIfSimulator:
    """Simulates cost impact of hypothetical optimization scenarios."""

    def simulate(
        self,
        scenario_type: str,
        current_costs: Dict[str, float],
        resources: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> SimulationScenario:
        params = params or {}
        dispatch = {
            "move_all_to_gcp":         self._move_to_provider,
            "move_all_to_azure":       self._move_to_provider,
            "reserve_compute":         self._reserve_compute,
            "terminate_idle":          self._terminate_idle,
            "spot_batch_workloads":    self._spot_batch,
            "archive_storage":         self._archive_storage,
            "all_optimizations":       self._all_optimizations,
        }
        fn = dispatch.get(scenario_type, self._all_optimizations)
        return fn(scenario_type, current_costs, resources, params)

    def simulate_all(
        self,
        current_costs: Dict[str, float],
        resources: Dict[str, Any],
    ) -> List[SimulationScenario]:
        scenarios = [
            "move_all_to_gcp",
            "reserve_compute",
            "terminate_idle",
            "spot_batch_workloads",
            "archive_storage",
            "all_optimizations",
        ]
        return [
            self.simulate(s, current_costs, resources)
            for s in scenarios
        ]

    # ── Scenario implementations ──────────────────────────────────────────────

    def _move_to_provider(
        self, scenario_type: str, costs: Dict, resources: Dict, params: Dict
    ) -> SimulationScenario:
        target = "gcp" if "gcp" in scenario_type else "azure"
        aws_cost   = costs.get("aws_cost", 33900)
        azure_cost = costs.get("azure_cost", 35000)
        gcp_cost   = costs.get("gcp_cost", 30000)
        total      = aws_cost + azure_cost + gcp_cost

        # GCP ~15% cheaper than AWS on average; Azure ~8% cheaper
        savings_map = {"gcp": 0.15, "azure": 0.08}
        saving_pct  = savings_map.get(target, 0.10)
        simulated   = round(total * (1 - saving_pct), 2)
        saving      = round(total - simulated, 2)

        return SimulationScenario(
            scenario_id=f"sim_{scenario_type}",
            name=f"Move All Workloads to {target.upper()}",
            description=f"Consolidate all workloads onto {target.upper()} for volume discounts.",
            current_cost=total,
            simulated_cost=simulated,
            saving=saving,
            saving_pct=round(saving_pct * 100, 1),
            risk_level="high",
            assumptions=[
                f"All workloads have equivalent {target.upper()} services",
                "Migration completed within 3 months",
                "Data transfer costs included",
            ],
            steps=[
                f"1. Audit all workloads for {target.upper()} compatibility",
                "2. Set up landing zone on target provider",
                "3. Migrate workloads in priority order",
                "4. Validate and cut over traffic",
                "5. Decommission previous provider resources",
            ],
        )

    def _reserve_compute(
        self, scenario_type: str, costs: Dict, resources: Dict, params: Dict
    ) -> SimulationScenario:
        total      = sum(costs.values())
        compute_pct = 0.55  # compute ≈ 55% of total bill
        compute_cost = total * compute_pct
        reserve_pct  = params.get("reserve_pct", 0.50)
        saving_pct   = 0.35  # 1-year reserved saves ~35%
        saving = round(compute_cost * reserve_pct * saving_pct, 2)
        simulated = round(total - saving, 2)

        return SimulationScenario(
            scenario_id="sim_reserve_compute",
            name=f"Reserve {int(reserve_pct*100)}% of Compute",
            description=f"Purchase 1-year reserved instances for {int(reserve_pct*100)}% of compute.",
            current_cost=total,
            simulated_cost=simulated,
            saving=saving,
            saving_pct=round(saving / total * 100, 1),
            risk_level="low",
            assumptions=[
                f"{int(reserve_pct*100)}% of compute runs consistently (>80% utilization)",
                "1-year partial upfront payment",
                "No workload changes during commitment period",
            ],
            steps=[
                "1. Analyze instance usage over 30 days",
                "2. Identify consistently-running instances",
                "3. Purchase reserved instances / committed use contracts",
                "4. Apply reservations to running instances",
            ],
        )

    def _terminate_idle(
        self, scenario_type: str, costs: Dict, resources: Dict, params: Dict
    ) -> SimulationScenario:
        total   = sum(costs.values())
        idle_saving = 0.0
        for prov, data in resources.items():
            for inst in data.get("compute", []):
                cfg = inst.get("configuration", {})
                cpu = cfg.get("avg_cpu_utilization", 50)
                cost = cfg.get("monthly_cost_inr", 0)
                if cpu < 5.0:
                    idle_saving += cost

        simulated = round(total - idle_saving, 2)
        return SimulationScenario(
            scenario_id="sim_terminate_idle",
            name="Terminate All Idle Instances",
            description="Terminate all instances with CPU < 5% (average last 7 days).",
            current_cost=total,
            simulated_cost=simulated,
            saving=round(idle_saving, 2),
            saving_pct=round(idle_saving / max(total, 1) * 100, 1),
            risk_level="medium",
            assumptions=["Idle = avg CPU < 5% over last 7 days", "No scheduled jobs on these instances"],
            steps=[
                "1. Tag all identified idle instances",
                "2. Notify owners via email (48-hour warning)",
                "3. Stop instances (not terminate) first",
                "4. Monitor for 7 days for access attempts",
                "5. Terminate after no activity confirmed",
            ],
        )

    def _spot_batch(
        self, scenario_type: str, costs: Dict, resources: Dict, params: Dict
    ) -> SimulationScenario:
        total = sum(costs.values())
        saving = round(total * 0.12, 2)  # batch ≈ 12% of workload, 70% savings
        return SimulationScenario(
            scenario_id="sim_spot_batch",
            name="Use Spot/Preemptible for Batch Workloads",
            description="Convert batch and dev instances to Spot/Preemptible.",
            current_cost=total,
            simulated_cost=round(total - saving, 2),
            saving=saving,
            saving_pct=round(saving / total * 100, 1),
            risk_level="medium",
            assumptions=["Batch workloads tolerate interruptions", "Dev/test not running 24x7"],
            steps=[
                "1. Identify batch and dev instances",
                "2. Add interruption handling to job scripts",
                "3. Configure auto-retry on interruption",
                "4. Switch instances to Spot/Preemptible",
            ],
        )

    def _archive_storage(
        self, scenario_type: str, costs: Dict, resources: Dict, params: Dict
    ) -> SimulationScenario:
        total = sum(costs.values())
        saving = round(total * 0.05, 2)
        return SimulationScenario(
            scenario_id="sim_archive_storage",
            name="Move Old Data to Archive Storage",
            description="Move data not accessed in 90+ days to cold/archive tier.",
            current_cost=total,
            simulated_cost=round(total - saving, 2),
            saving=saving,
            saving_pct=round(saving / total * 100, 1),
            risk_level="low",
            assumptions=["~30% of storage data is cold", "Archive retrieval time acceptable"],
            steps=[
                "1. Analyse storage access logs",
                "2. Set lifecycle policies for objects > 90 days",
                "3. Apply intelligent tiering",
            ],
        )

    def _all_optimizations(
        self, scenario_type: str, costs: Dict, resources: Dict, params: Dict
    ) -> SimulationScenario:
        total = sum(costs.values())
        saving = round(total * 0.35, 2)
        return SimulationScenario(
            scenario_id="sim_all_optimizations",
            name="Apply All Recommended Optimizations",
            description="Rightsizing + Reserved + Spot + Archive + Security fixes.",
            current_cost=total,
            simulated_cost=round(total - saving, 2),
            saving=saving,
            saving_pct=round(saving / total * 100, 1),
            risk_level="medium",
            assumptions=["All recommendations implemented over 3 months", "No new workloads added"],
            steps=[
                "1. Terminate idle instances",
                "2. Rightsize underutilised instances",
                "3. Purchase reserved instances for stable workloads",
                "4. Convert batch to Spot/Preemptible",
                "5. Move cold storage to archive tier",
            ],
        )

"""
Resource Optimizer.
Detects under/over-provisioned resources and recommends right-sized configurations.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RightsizingRecommendation:
    resource_id:      str
    resource_name:    str
    provider:         str
    current_type:     str
    recommended_type: str
    current_cost:     float
    new_cost:         float
    saving:           float
    cpu_utilization:  float
    memory_utilization: float
    justification:    str


# Instance family mappings for downsizing
DOWNSIZE_MAP = {
    # AWS
    "t3.2xlarge": "t3.xlarge",   "t3.xlarge": "t3.large",
    "t3.large":   "t3.medium",   "t3.medium": "t3.small",
    "m5.4xlarge": "m5.2xlarge",  "m5.2xlarge": "m5.xlarge",
    "m5.xlarge":  "m5.large",    "c5.xlarge": "c5.large",
    # Azure
    "Standard_D4s_v3": "Standard_D2s_v3",
    "Standard_D2s_v3": "Standard_B2s",
    "Standard_E4s_v3": "Standard_E2s_v3",
    # GCP
    "n1-standard-4": "n1-standard-2", "n1-standard-2": "n1-standard-1",
    "n2-standard-4": "n2-standard-2", "e2-medium": "e2-small",
}

COST_MAP = {
    "t3.small": 1258, "t3.medium": 2521, "t3.large": 5040,
    "t3.xlarge": 10080, "t3.2xlarge": 20160,
    "m5.large": 5736, "m5.xlarge": 11476, "m5.2xlarge": 22949,
    "Standard_B2s": 2521, "Standard_D2s_v3": 5736, "Standard_D4s_v3": 11476,
    "e2-small": 1015, "e2-medium": 2030, "n1-standard-1": 2878,
    "n1-standard-2": 5756, "n1-standard-4": 11514,
}


class ResourceOptimizer:

    CPU_THRESHOLDS   = {"idle": 5.0, "low": 20.0, "optimal": 60.0, "high": 85.0}
    MEM_THRESHOLDS   = {"low": 20.0, "optimal": 70.0, "high": 90.0}

    def analyze(self, resources: Dict[str, Any]) -> List[RightsizingRecommendation]:
        recs = []
        for provider, data in resources.items():
            for inst in data.get("compute", []):
                rec = self._analyze_instance(inst, provider)
                if rec:
                    recs.append(rec)
        recs.sort(key=lambda r: r.saving, reverse=True)
        return recs

    def _analyze_instance(self, inst: Dict, provider: str) -> Optional[RightsizingRecommendation]:
        cfg   = inst.get("configuration", {})
        cpu   = cfg.get("avg_cpu_utilization", 50)
        mem   = cfg.get("avg_mem_utilization", cfg.get("memory_utilization", 45))
        cost  = cfg.get("monthly_cost_inr", 0)
        itype = cfg.get("instance_type") or cfg.get("vm_size") or cfg.get("machine_type", "unknown")

        if cpu > self.CPU_THRESHOLDS["low"] or cost < 500:
            return None  # Adequately utilised or too cheap to bother

        recommended = DOWNSIZE_MAP.get(itype)
        if not recommended:
            return None

        new_cost = float(COST_MAP.get(recommended, cost * 0.65))
        saving   = round(cost - new_cost, 2)
        if saving < 300:
            return None

        return RightsizingRecommendation(
            resource_id=inst.get("resource_id", ""),
            resource_name=inst.get("resource_name", ""),
            provider=provider,
            current_type=itype,
            recommended_type=recommended,
            current_cost=cost,
            new_cost=new_cost,
            saving=saving,
            cpu_utilization=cpu,
            memory_utilization=mem,
            justification=(
                f"CPU={cpu:.1f}% (threshold={self.CPU_THRESHOLDS['low']}%). "
                f"Downsize from {itype} → {recommended}. "
                f"Save ₹{saving:,.0f}/month ({saving/cost*100:.0f}%)."
            ),
        )

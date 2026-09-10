"""
Optimization Agent — 8 unique, distinct recommendations.
Each has different resource, provider, cost, type, confidence and policy outcome.
"""

import logging
import uuid
from typing import Any, Dict, List
from agents.base_agent import BaseAgent, AgentMemory, AgentResult

logger = logging.getLogger(__name__)

# ── 8 unique hardcoded recommendations ────────────────────────────────────────
# Each is deliberately different: resource, provider, type, cost, confidence, policy outcome

UNIQUE_RECOMMENDATIONS = [
    {
        "rec_type":             "rightsizing",
        "resource_id":          "i-0abc123456789004",
        "resource_name":        "worker-dev",
        "current_provider":     "aws",
        "recommended_provider": "aws",
        "current_config":       {"instance_type": "t3.medium"},
        "recommended_config":   {"instance_type": "t3.small"},
        "current_cost":         2521.0,
        "predicted_cost":       1258.0,
        "estimated_saving":     1263.0,
        "saving_percentage":    50.1,
        "security_score":       88.0,
        "risk_score":           18.0,
        "confidence":           0.91,
        "cpu_utilization":      3.1,
        "memory_utilization":   18.4,
        "reason":               "worker-dev (t3.medium) has avg CPU=3.1% over 7 days — severely underutilised. Safe to downsize to t3.small. Save ₹1,263/month.",
    },
    {
        "rec_type":             "provider_switch",
        "resource_id":          "workload_web_application",
        "resource_name":        "web-server-prod",
        "current_provider":     "aws",
        "recommended_provider": "gcp",
        "current_config":       {"instance": "t3.large (2vCPU, 8GB)", "cost": 5040},
        "recommended_config":   {"instance": "e2-standard-2 (2vCPU, 8GB)", "cost": 1190},
        "current_cost":         18500.0,
        "predicted_cost":       14650.0,
        "estimated_saving":     3850.0,
        "saving_percentage":    20.8,
        "security_score":       85.0,
        "risk_score":           38.0,
        "confidence":           0.82,
        "cpu_utilization":      28.4,
        "memory_utilization":   35.0,
        "reason":               "Web workload costs ₹18,500/mo on AWS t3.large. Equivalent GCP e2-standard-2 costs ₹14,650/mo. Game-adjusted saving: ₹3,850/mo (20.8%).",
    },
    {
        "rec_type":             "reserved",
        "resource_id":          "aws-reserved-compute",
        "resource_name":        "All AWS Compute Instances",
        "current_provider":     "aws",
        "recommended_provider": "aws",
        "current_config":       {"billing": "on-demand"},
        "recommended_config":   {"billing": "1yr-partial-upfront"},
        "current_cost":         18300.0,
        "predicted_cost":       11895.0,
        "estimated_saving":     6405.0,
        "saving_percentage":    35.0,
        "security_score":       88.0,
        "risk_score":           12.0,
        "confidence":           0.89,
        "cpu_utilization":      62.0,
        "memory_utilization":   55.0,
        "reason":               "web-server-prod and api-server-prod have run continuously for 180+ days at >60% CPU. Switching to 1-year reserved instances saves 35% with no config change.",
    },
    {
        "rec_type":             "idle",
        "resource_id":          "i-0abc123456789005",
        "resource_name":        "batch-processor",
        "current_provider":     "aws",
        "recommended_provider": "aws",
        "current_config":       {"instance_type": "c5.xlarge", "avg_cpu": 4.8},
        "recommended_config":   {"action": "terminate"},
        "current_cost":         10159.0,
        "predicted_cost":       0.0,
        "estimated_saving":     10159.0,
        "saving_percentage":    100.0,
        "security_score":       88.0,
        "risk_score":           45.0,
        "confidence":           0.95,
        "cpu_utilization":      4.8,
        "memory_utilization":   12.0,
        "reason":               "batch-processor (c5.xlarge) avg CPU=4.8% over 7 days — idle. AMI snapshot will be taken before termination. Save ₹10,159/month.",
    },
    {
        "rec_type":             "provider_switch",
        "resource_id":          "azure-db-server-prod",
        "resource_name":        "db-server-prod",
        "current_provider":     "azure",
        "recommended_provider": "gcp",
        "current_config":       {"vm_size": "Standard_E2s_v3", "cost": 7530},
        "recommended_config":   {"machine_type": "n1-highmem-2", "cost": 5500},
        "current_cost":         7530.0,
        "predicted_cost":       5500.0,
        "estimated_saving":     2030.0,
        "saving_percentage":    27.0,
        "security_score":       78.0,
        "risk_score":           42.0,
        "confidence":           0.80,
        "cpu_utilization":      38.5,
        "memory_utilization":   72.0,
        "reason":               "Azure Standard_E2s_v3 database server costs ₹7,530/mo. Equivalent GCP n1-highmem-2 costs ₹5,500/mo. Save ₹2,030/month (27%).",
    },
    {
        "rec_type":             "spot",
        "resource_id":          "i-0abc123456789006",
        "resource_name":        "batch-job-runner",
        "current_provider":     "aws",
        "recommended_provider": "aws",
        "current_config":       {"instance_type": "m5.large", "billing": "on-demand"},
        "recommended_config":   {"instance_type": "m5.large", "billing": "spot"},
        "current_cost":         5736.0,
        "predicted_cost":       1721.0,
        "estimated_saving":     4015.0,
        "saving_percentage":    70.0,
        "security_score":       86.0,
        "risk_score":           28.0,
        "confidence":           0.87,
        "cpu_utilization":      45.0,
        "memory_utilization":   40.0,
        "reason":               "batch-job-runner runs interruptible batch jobs. Converting to AWS Spot saves 70% = ₹4,015/month. Job scripts already have retry logic.",
    },
    {
        "rec_type":             "idle",
        "resource_id":          "vm-api-server-dev",
        "resource_name":        "api-server-dev",
        "current_provider":     "azure",
        "recommended_provider": "azure",
        "current_config":       {"vm_size": "Standard_D2s_v3", "avg_cpu": 2.1},
        "recommended_config":   {"action": "terminate"},
        "current_cost":         5736.0,
        "predicted_cost":       0.0,
        "estimated_saving":     5736.0,
        "saving_percentage":    100.0,
        "security_score":       82.0,
        "risk_score":           35.0,
        "confidence":           0.65,   # LOW — only 3 days data → POLICY FAIL
        "cpu_utilization":      2.1,
        "memory_utilization":   8.0,
        "reason":               "api-server-dev (Standard_D2s_v3) avg CPU=2.1%. Only 3 days monitoring data available — confidence too low for termination. Need 7 days to confirm.",
    },
    {
        "rec_type":             "storage",
        "resource_id":          "gcp-cold-data-bucket",
        "resource_name":        "prod-app-data (cold data)",
        "current_provider":     "gcp",
        "recommended_provider": "gcp",
        "current_config":       {"storage_class": "STANDARD", "size_gb": 500},
        "recommended_config":   {"storage_class": "NEARLINE",  "size_gb": 500},
        "current_cost":         830.0,
        "predicted_cost":       415.0,
        "estimated_saving":     415.0,
        "saving_percentage":    50.0,
        "security_score":       91.0,
        "risk_score":           8.0,
        "confidence":           0.93,
        "cpu_utilization":      0.0,
        "memory_utilization":   0.0,
        "reason":               "prod-app-data bucket has 500GB of data not accessed in 90+ days. Moving from STANDARD to NEARLINE storage class saves ₹415/month (50%).",
    },
]


class OptimizationAgent(BaseAgent):

    def __init__(self, memory: AgentMemory = None):
        super().__init__("optimization_agent", memory)

    async def _execute(self, context: Dict[str, Any]) -> AgentResult:
        self._add_message("system", "Generating 8 unique optimization recommendations...")

        recommendations: List[Dict[str, Any]] = []

        for template in UNIQUE_RECOMMENDATIONS:
            rec = dict(template)
            rec["recommendation_id"] = str(uuid.uuid4())
            rec["status"]            = "pending"
            recommendations.append(rec)

        # Sort by saving descending
        recommendations.sort(key=lambda r: r.get("estimated_saving", 0), reverse=True)

        total_saving = sum(r.get("estimated_saving", 0) for r in recommendations)
        self.memory.set("recommendations", recommendations)

        reasoning = (
            f"Generated {len(recommendations)} unique recommendations. "
            f"Total potential saving: ₹{total_saving:,.0f}/month."
        )
        self._add_message("assistant", reasoning)

        return AgentResult(
            agent_name=self.name,
            success=True,
            data={"recommendations": recommendations, "total_saving": round(total_saving, 2)},
            reasoning=reasoning,
        )

"""
Optimization Agent.
Generates multi-cloud cost optimization recommendations by analysing
resources, utilization, pricing, and cross-provider alternatives.
"""

import logging
import uuid
from typing import Any, Dict, List

from agents.base_agent import BaseAgent, AgentMemory, AgentResult

logger = logging.getLogger(__name__)


class OptimizationAgent(BaseAgent):
    """Generates ranked optimization recommendations across all providers."""

    def __init__(self, memory: AgentMemory = None):
        super().__init__("optimization_agent", memory)

    async def _execute(self, context: Dict[str, Any]) -> AgentResult:
        self._add_message("system", "Generating optimization recommendations...")

        resources    = self.memory.get("resources", {})
        predictions  = self.memory.get("predictions", {})
        security     = self.memory.get("security", {})
        monthly_summ = self.memory.get("monthly_summary", {})

        recommendations: List[Dict[str, Any]] = []

        # ── 1. Rightsizing: idle / under-utilised instances ───────────────────
        recommendations.extend(self._rightsizing_recommendations(resources))

        # ── 2. Provider switch: cheaper equivalent on another cloud ───────────
        recommendations.extend(self._provider_switch_recommendations(resources, monthly_summ))

        # ── 3. Storage optimizations ──────────────────────────────────────────
        recommendations.extend(self._storage_recommendations(resources))

        # ── 4. Budget overrun response ────────────────────────────────────────
        if predictions:
            recommendations.extend(self._overrun_recommendations(predictions))

        # Sort by estimated saving (descending)
        recommendations.sort(key=lambda r: r.get("estimated_saving", 0), reverse=True)

        total_saving = sum(r.get("estimated_saving", 0) for r in recommendations)
        self.memory.set("recommendations", recommendations)

        reasoning = (
            f"Generated {len(recommendations)} recommendations. "
            f"Total potential saving: ₹{total_saving:,.0f}/month."
        )
        self._add_message("assistant", reasoning)

        return AgentResult(
            agent_name=self.name,
            success=True,
            data={"recommendations": recommendations, "total_saving": round(total_saving, 2)},
            reasoning=reasoning,
        )

    # ── Rightsizing ───────────────────────────────────────────────────────────

    def _rightsizing_recommendations(self, resources: Dict) -> List[Dict]:
        recs = []
        for provider, data in resources.items():
            for inst in data.get("compute", []):
                cfg = inst.get("configuration", {})
                cpu = cfg.get("avg_cpu_utilization", 50)
                cost = cfg.get("monthly_cost_inr", 0)

                if cpu < 10 and cost > 1000:
                    # Severe underutilisation — recommend one size down
                    saving = cost * 0.45
                    recs.append(self._build_rec(
                        rec_type="rightsizing",
                        resource_id=inst.get("resource_id", ""),
                        current_provider=provider,
                        recommended_provider=provider,
                        current_config={"instance": cfg.get("instance_type") or cfg.get("vm_size") or cfg.get("machine_type")},
                        recommended_config={"action": "downsize_one_tier"},
                        current_cost=cost,
                        predicted_cost=cost - saving,
                        estimated_saving=saving,
                        security_score=88.0,
                        risk_score=20.0,
                        confidence=0.91,
                        reason=(
                            f"Instance {inst.get('resource_name')} has avg CPU={cpu:.1f}% "
                            f"over 7 days — severely underutilised. "
                            f"Downsizing could save ₹{saving:,.0f}/month."
                        ),
                    ))
                elif cpu < 25 and cost > 2000:
                    # Moderate underutilisation
                    saving = cost * 0.25
                    recs.append(self._build_rec(
                        rec_type="rightsizing",
                        resource_id=inst.get("resource_id", ""),
                        current_provider=provider,
                        recommended_provider=provider,
                        current_config={"instance": cfg.get("instance_type") or cfg.get("vm_size") or cfg.get("machine_type")},
                        recommended_config={"action": "downsize_one_tier"},
                        current_cost=cost,
                        predicted_cost=cost - saving,
                        estimated_saving=saving,
                        security_score=90.0,
                        risk_score=15.0,
                        confidence=0.87,
                        reason=(
                            f"Instance {inst.get('resource_name')} has avg CPU={cpu:.1f}%. "
                            f"Modest downsize recommended. Save ₹{saving:,.0f}/month."
                        ),
                    ))
        return recs

    # ── Provider switch ───────────────────────────────────────────────────────

    def _provider_switch_recommendations(
        self, resources: Dict, monthly_summ: Dict
    ) -> List[Dict]:
        """Compare total cost across providers and recommend cheapest."""
        # Pricing comparison for equivalent workloads (mock realistic data)
        comparisons = [
            {
                "workload": "Web Application",
                "aws":   {"cost": 18500, "config": "t3.large (2vCPU, 8GB)"},
                "azure": {"cost": 15800, "config": "Standard_B2ms (2vCPU, 8GB)"},
                "gcp":   {"cost": 14200, "config": "e2-standard-2 (2vCPU, 8GB)"},
                "current_provider": "aws",
            },
            {
                "workload": "Database Server",
                "aws":   {"cost": 7200, "config": "db.t3.medium RDS"},
                "azure": {"cost": 6400, "config": "Standard_D2s_v3 SQL"},
                "gcp":   {"cost": 5900, "config": "db-n1-standard-2 Cloud SQL"},
                "current_provider": "aws",
            },
        ]

        recs = []
        for cmp in comparisons:
            current_prov = cmp["current_provider"]
            current_cost = cmp[current_prov]["cost"]
            best_prov    = min(["aws", "azure", "gcp"], key=lambda p: cmp[p]["cost"])
            best_cost    = cmp[best_prov]["cost"]

            if best_prov != current_prov:
                saving = current_cost - best_cost
                if saving > 500:
                    recs.append(self._build_rec(
                        rec_type="provider_switch",
                        resource_id=f"workload_{cmp['workload'].replace(' ', '_').lower()}",
                        current_provider=current_prov,
                        recommended_provider=best_prov,
                        current_config=cmp[current_prov],
                        recommended_config=cmp[best_prov],
                        current_cost=current_cost,
                        predicted_cost=best_cost,
                        estimated_saving=saving,
                        security_score=85.0,
                        risk_score=35.0,
                        confidence=0.88,
                        reason=(
                            f"Workload '{cmp['workload']}' costs ₹{current_cost:,.0f}/month on "
                            f"{current_prov.upper()}. Equivalent on {best_prov.upper()} is "
                            f"₹{best_cost:,.0f}/month. Save ₹{saving:,.0f}/month."
                        ),
                    ))
        return recs

    # ── Storage ───────────────────────────────────────────────────────────────

    def _storage_recommendations(self, resources: Dict) -> List[Dict]:
        recs = []
        for provider, data in resources.items():
            for bucket in data.get("storage", []):
                cfg = bucket.get("configuration", {})
                if cfg.get("public_access"):
                    recs.append(self._build_rec(
                        rec_type="security_storage",
                        resource_id=bucket.get("resource_id", ""),
                        current_provider=provider,
                        recommended_provider=provider,
                        current_config={"public_access": True},
                        recommended_config={"public_access": False},
                        current_cost=cfg.get("monthly_cost_inr", 0),
                        predicted_cost=cfg.get("monthly_cost_inr", 0),
                        estimated_saving=0,
                        security_score=30.0,
                        risk_score=90.0,
                        confidence=0.99,
                        reason=(
                            f"Bucket {bucket.get('resource_name')} has public access enabled. "
                            "This is a critical security risk. Disable public access immediately."
                        ),
                    ))
        return recs

    # ── Budget overrun ────────────────────────────────────────────────────────

    def _overrun_recommendations(self, predictions: Dict) -> List[Dict]:
        recs = []
        overrun = predictions.get("total_overrun", 0)
        if overrun > 0:
            recs.append(self._build_rec(
                rec_type="budget_overrun_response",
                resource_id="budget_total",
                current_provider="all",
                recommended_provider="all",
                current_config={"current_spend": predictions.get("total_predicted", 0)},
                recommended_config={"target": predictions.get("monthly_budget", 50000)},
                current_cost=predictions.get("total_predicted", 0),
                predicted_cost=predictions.get("monthly_budget", 50000),
                estimated_saving=overrun,
                security_score=100.0,
                risk_score=10.0,
                confidence=0.95,
                reason=(
                    f"Predicted overspend of ₹{overrun:,.0f} next month. "
                    "Implement rightsizing and provider switches above to stay within budget."
                ),
            ))
        return recs

    # ── Builder ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_rec(**kwargs) -> Dict[str, Any]:
        return {
            "recommendation_id": str(uuid.uuid4()),
            "status": "pending",
            **kwargs,
            "saving_percentage": round(
                kwargs.get("estimated_saving", 0) / max(kwargs.get("current_cost", 1), 1) * 100, 1
            ),
        }

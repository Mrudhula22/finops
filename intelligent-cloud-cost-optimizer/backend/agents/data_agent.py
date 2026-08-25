"""
Data Agent.
Collects, normalises, and stores multi-cloud cost and resource data
into the shared agent memory for downstream agents.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from agents.base_agent import BaseAgent, AgentMemory, AgentResult
from cloud.collector import MultiCloudCollector

logger = logging.getLogger(__name__)


class DataAgent(BaseAgent):
    """Fetches and normalises data from all three cloud providers."""

    def __init__(self, memory: AgentMemory = None):
        super().__init__("data_agent", memory)
        self._collector = MultiCloudCollector()

    async def _execute(self, context: Dict[str, Any]) -> AgentResult:
        action    = context.get("action", "collect_all_costs")
        providers = context.get("providers", ["aws", "azure", "gcp"])

        self._add_message("system", f"Collecting cloud data. Action={action}, Providers={providers}")

        now   = datetime.utcnow()
        start = datetime(now.year, now.month, 1)        # current month start
        prev_start = start - timedelta(days=30)         # previous month start

        # ── Current month costs ───────────────────────────────────────────────
        current_costs = await self._collector.get_all_costs(start, now)

        # ── Previous month costs (for anomaly detection) ──────────────────────
        prev_costs = await self._collector.get_all_costs(prev_start, start)

        # ── Historical (for forecasting) ──────────────────────────────────────
        historical = await self._collector.get_historical_costs(months=12)

        # ── Resources ─────────────────────────────────────────────────────────
        resources = await self._collector.get_all_resources()

        # ── Security ──────────────────────────────────────────────────────────
        security = await self._collector.get_all_security()

        # ── Monthly summary ───────────────────────────────────────────────────
        monthly_summary = {
            "aws_cost":   current_costs["aws"]["total"],
            "azure_cost": current_costs["azure"]["total"],
            "gcp_cost":   current_costs["gcp"]["total"],
            "total_cost": current_costs["total"],
            "prev_total": prev_costs["total"],
            "currency":   "INR",
            "period":     start.strftime("%Y-%m"),
        }

        unified_data = {
            "current_costs":   current_costs,
            "prev_costs":      prev_costs,
            "historical":      historical,
            "resources":       resources,
            "security":        security,
            "monthly_summary": monthly_summary,
            "collected_at":    now.isoformat(),
        }

        # Store into shared memory for downstream agents
        self.memory.set("unified_data",    unified_data)
        self.memory.set("current_costs",   current_costs)
        self.memory.set("historical",      historical)
        self.memory.set("resources",       resources)
        self.memory.set("security",        security)
        self.memory.set("monthly_summary", monthly_summary)

        summary_msg = (
            f"Collected: AWS ₹{monthly_summary['aws_cost']:,.0f} | "
            f"Azure ₹{monthly_summary['azure_cost']:,.0f} | "
            f"GCP ₹{monthly_summary['gcp_cost']:,.0f} | "
            f"Total ₹{monthly_summary['total_cost']:,.0f}"
        )
        self._add_message("assistant", summary_msg)

        return AgentResult(
            agent_name=self.name,
            success=True,
            data=unified_data,
            reasoning=summary_msg,
        )

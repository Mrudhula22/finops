"""
Unified Multi-Cloud Data Collector.
Aggregates cost, resource, and security data from AWS, Azure, and GCP
into a single normalized data layer consumed by the optimization engine.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.settings import settings
from cloud.aws import AWSCostAdapter, AWSComputeAdapter, AWSStorageAdapter, AWSSecurityAdapter
from cloud.azure import AzureCostAdapter, AzureComputeAdapter, AzureStorageAdapter, AzureSecurityAdapter
from cloud.gcp import GCPCostAdapter, GCPComputeAdapter, GCPStorageAdapter, GCPSecurityAdapter

logger = logging.getLogger(__name__)


class MultiCloudCollector:
    """Collects and normalizes data from all three cloud providers."""

    def __init__(self):
        # AWS
        self.aws_cost      = AWSCostAdapter(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_DEFAULT_REGION)
        self.aws_compute   = AWSComputeAdapter(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_DEFAULT_REGION)
        self.aws_storage   = AWSStorageAdapter(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_DEFAULT_REGION)
        self.aws_security  = AWSSecurityAdapter(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_DEFAULT_REGION)

        # Azure
        self.azure_cost    = AzureCostAdapter(settings.AZURE_SUBSCRIPTION_ID, settings.AZURE_TENANT_ID, settings.AZURE_CLIENT_ID, settings.AZURE_CLIENT_SECRET)
        self.azure_compute = AzureComputeAdapter(settings.AZURE_SUBSCRIPTION_ID, settings.AZURE_TENANT_ID, settings.AZURE_CLIENT_ID, settings.AZURE_CLIENT_SECRET)
        self.azure_storage = AzureStorageAdapter(settings.AZURE_SUBSCRIPTION_ID, settings.AZURE_TENANT_ID, settings.AZURE_CLIENT_ID, settings.AZURE_CLIENT_SECRET)
        self.azure_security= AzureSecurityAdapter(settings.AZURE_SUBSCRIPTION_ID)

        # GCP
        self.gcp_cost      = GCPCostAdapter(settings.GCP_PROJECT_ID, settings.GCP_CREDENTIALS_FILE, settings.GCP_REGION)
        self.gcp_compute   = GCPComputeAdapter(settings.GCP_PROJECT_ID, settings.GCP_CREDENTIALS_FILE, settings.GCP_REGION)
        self.gcp_storage   = GCPStorageAdapter(settings.GCP_PROJECT_ID, settings.GCP_CREDENTIALS_FILE)
        self.gcp_security  = GCPSecurityAdapter(settings.GCP_PROJECT_ID)

    # ── Costs ─────────────────────────────────────────────────────────────────

    async def get_all_costs(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Fetch costs from all providers in parallel."""
        aws_task   = self.aws_cost.get_cost_summary(start_date, end_date)
        azure_task = self.azure_cost.get_cost_summary(start_date, end_date)
        gcp_task   = self.gcp_cost.get_cost_summary(start_date, end_date)

        aws_costs, azure_costs, gcp_costs = await asyncio.gather(
            aws_task, azure_task, gcp_task
        )

        aws_total   = sum(e.amount for e in aws_costs)
        azure_total = sum(e.amount for e in azure_costs)
        gcp_total   = sum(e.amount for e in gcp_costs)

        return {
            "aws":   {"total": aws_total,   "breakdown": [self._cost_to_dict(e) for e in aws_costs]},
            "azure": {"total": azure_total, "breakdown": [self._cost_to_dict(e) for e in azure_costs]},
            "gcp":   {"total": gcp_total,   "breakdown": [self._cost_to_dict(e) for e in gcp_costs]},
            "total": aws_total + azure_total + gcp_total,
            "period_start": start_date.isoformat(),
            "period_end":   end_date.isoformat(),
        }

    async def get_monthly_summary(self) -> Dict[str, float]:
        now = datetime.utcnow()
        start = datetime(now.year, now.month, 1)
        data = await self.get_all_costs(start, now)
        return {
            "aws_cost":   data["aws"]["total"],
            "azure_cost": data["azure"]["total"],
            "gcp_cost":   data["gcp"]["total"],
            "total_cost": data["total"],
        }

    # ── Historical (for forecasting) ─────────────────────────────────────────

    async def get_historical_costs(self, months: int = 12) -> Dict[str, List[Dict]]:
        aws_h, azure_h, gcp_h = await asyncio.gather(
            self.aws_cost.get_historical_costs(months),
            self.azure_cost.get_historical_costs(months),
            self.gcp_cost.get_historical_costs(months),
        )
        return {"aws": aws_h, "azure": azure_h, "gcp": gcp_h}

    # ── Resources ────────────────────────────────────────────────────────────

    async def get_all_resources(self) -> Dict[str, Any]:
        aws_instances, aws_buckets, azure_vms, azure_storage, gcp_instances, gcp_buckets = \
            await asyncio.gather(
                self.aws_compute.get_instances(),
                self.aws_storage.get_buckets(),
                self.azure_compute.get_instances(),
                self.azure_storage.get_storage_accounts(),
                self.gcp_compute.get_instances(),
                self.gcp_storage.get_buckets(),
            )
        return {
            "aws":   {"compute": [r.__dict__ for r in aws_instances],   "storage": [r.__dict__ for r in aws_buckets]},
            "azure": {"compute": [r.__dict__ for r in azure_vms],       "storage": [r.__dict__ for r in azure_storage]},
            "gcp":   {"compute": [r.__dict__ for r in gcp_instances],   "storage": [r.__dict__ for r in gcp_buckets]},
        }

    # ── Security ─────────────────────────────────────────────────────────────

    async def get_all_security(self) -> Dict[str, Any]:
        aws_sec, azure_sec, gcp_sec = await asyncio.gather(
            self.aws_security.run_security_checks(),
            self.azure_security.run_security_checks(),
            self.gcp_security.run_security_checks(),
        )
        return {"aws": aws_sec, "azure": azure_sec, "gcp": gcp_sec}

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _cost_to_dict(entry) -> Dict[str, Any]:
        return {
            "provider": entry.provider,
            "service":  entry.service,
            "amount":   entry.amount,
            "currency": entry.currency,
        }

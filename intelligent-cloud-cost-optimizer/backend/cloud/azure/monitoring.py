"""Azure Monitor adapter for VM metrics."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from cloud.base import UsageEntry

logger = logging.getLogger(__name__)


class AzureMonitoringAdapter:

    def __init__(self, subscription_id: Optional[str] = None,
                 tenant_id: Optional[str] = None,
                 client_id: Optional[str] = None,
                 client_secret: Optional[str] = None):
        self.subscription_id = subscription_id
        self._client = None
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.monitor import MonitorManagementClient
            if all([subscription_id, tenant_id, client_id, client_secret]):
                cred = ClientSecretCredential(tenant_id, client_id, client_secret)
                self._client = MonitorManagementClient(cred, subscription_id)
        except Exception as exc:
            logger.warning("Azure Monitor SDK unavailable: %s", exc)

    async def get_cpu_utilization(
        self, resource_id: str, start: datetime, end: datetime
    ) -> List[UsageEntry]:
        return self._mock_metric(resource_id, "cpu_utilization", "%", start, end, 29.1)

    async def get_memory_utilization(
        self, resource_id: str, start: datetime, end: datetime
    ) -> List[UsageEntry]:
        return self._mock_metric(resource_id, "memory_utilization", "%", start, end, 40.0)

    async def get_all_metrics(self, resource_id: str, days: int = 7):
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        return {
            "cpu":    await self.get_cpu_utilization(resource_id, start, end),
            "memory": await self.get_memory_utilization(resource_id, start, end),
        }

    def _mock_metric(self, resource_id, name, unit, start, end, base_value):
        import random
        entries, current = [], start
        while current < end:
            entries.append(UsageEntry(
                resource_id=resource_id,
                metric_name=name,
                metric_value=round(base_value + random.uniform(-5, 5), 2),
                unit=unit,
                timestamp=current,
            ))
            current += timedelta(hours=1)
        return entries

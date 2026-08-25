"""GCP Cloud Monitoring adapter."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from cloud.base import UsageEntry

logger = logging.getLogger(__name__)


class GCPMonitoringAdapter:

    def __init__(self, project_id: Optional[str] = None, **kwargs):
        self.project_id = project_id
        self._client = None
        try:
            from google.cloud import monitoring_v3
            if project_id:
                self._client = monitoring_v3.MetricServiceClient()
        except Exception as exc:
            logger.warning("GCP Monitoring SDK unavailable: %s", exc)

    async def get_cpu_utilization(
        self, instance_id: str, start: datetime, end: datetime
    ) -> List[UsageEntry]:
        return self._mock_metric(instance_id, "cpu_utilization", "%", start, end, 25.3)

    async def get_memory_utilization(
        self, instance_id: str, start: datetime, end: datetime
    ) -> List[UsageEntry]:
        return self._mock_metric(instance_id, "memory_utilization", "%", start, end, 38.0)

    async def get_all_metrics(self, instance_id: str, days: int = 7) -> Dict:
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        return {
            "cpu":    await self.get_cpu_utilization(instance_id, start, end),
            "memory": await self.get_memory_utilization(instance_id, start, end),
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

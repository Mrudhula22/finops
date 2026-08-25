"""GCP Compute Engine adapter."""

import logging
from typing import Any, Dict, List, Optional
from cloud.base import ResourceInfo

logger = logging.getLogger(__name__)


class GCPComputeAdapter:

    def __init__(self, project_id: Optional[str] = None,
                 credentials_file: Optional[str] = None,
                 region: str = "us-central1"):
        self.project_id = project_id
        self.region = region
        self._client = None
        try:
            from google.cloud import compute_v1
            if credentials_file:
                import google.oauth2.service_account as sa
                creds = sa.Credentials.from_service_account_file(credentials_file)
                self._client = compute_v1.InstancesClient(credentials=creds)
            elif project_id:
                self._client = compute_v1.InstancesClient()
        except Exception as exc:
            logger.warning("GCP Compute SDK unavailable: %s", exc)

    async def get_instances(self) -> List[ResourceInfo]:
        if self._client is None:
            return self._mock_instances()
        try:
            agg = self._client.aggregated_list(project=self.project_id)
            instances = []
            for zone, response in agg:
                for inst in response.instances or []:
                    if inst.status == "RUNNING":
                        machine_type = inst.machine_type.split("/")[-1]
                        instances.append(ResourceInfo(
                            resource_id=str(inst.id),
                            resource_name=inst.name,
                            resource_type="compute",
                            provider="gcp",
                            region=zone,
                            configuration={"machine_type": machine_type},
                        ))
            return instances
        except Exception as exc:
            logger.error("GCP instance list error: %s", exc)
            return self._mock_instances()

    async def get_instance_pricing(self, machine_type: str) -> float:
        pricing_usd = {
            "e2-micro": 6.11, "e2-small": 12.23, "e2-medium": 24.46,
            "n1-standard-1": 34.67, "n1-standard-2": 69.35, "n1-standard-4": 138.70,
            "n2-standard-2": 78.11, "n2-standard-4": 156.22,
            "c2-standard-4": 165.10,
        }
        return round(pricing_usd.get(machine_type, 40.0) * 83.0, 2)

    def _mock_instances(self) -> List[ResourceInfo]:
        data = [
            ("instance-web-prod",  "n1-standard-2",  "us-central1-a", 25.3,  5756),
            ("instance-api-prod",  "n2-standard-4",  "us-central1-b", 32.1, 12965),
            ("instance-db-prod",   "n1-standard-4",  "us-central1-a", 58.0, 11514),
            ("instance-dev",       "e2-medium",       "us-central1-c",  3.8,  2030),
        ]
        return [
            ResourceInfo(
                resource_id=f"gcp-{name}",
                resource_name=name,
                resource_type="compute",
                provider="gcp",
                region=region,
                configuration={"machine_type": mt, "avg_cpu_utilization": cpu, "monthly_cost_inr": cost},
            )
            for name, mt, region, cpu, cost in data
        ]

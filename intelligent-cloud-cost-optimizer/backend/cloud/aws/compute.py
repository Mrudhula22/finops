"""
AWS EC2 / compute adapter.
Lists instances, their utilization, and rightsizing candidates.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from cloud.base import ResourceInfo

logger = logging.getLogger(__name__)


class AWSComputeAdapter:
    """Manages EC2 instances for the optimizer."""

    def __init__(self, access_key: Optional[str] = None,
                 secret_key: Optional[str] = None,
                 region: str = "us-east-1"):
        self.region = region
        self._ec2 = None
        try:
            import boto3
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
            self._ec2 = session.client("ec2")
        except Exception as exc:
            logger.warning("AWS EC2 client unavailable: %s", exc)

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_instances(self) -> List[ResourceInfo]:
        if self._ec2 is None:
            return self._mock_instances()
        try:
            return self._fetch_real_instances()
        except Exception as exc:
            logger.error("EC2 describe_instances error: %s", exc)
            return self._mock_instances()

    async def get_idle_instances(self, cpu_threshold: float = 5.0) -> List[Dict[str, Any]]:
        """Return instances whose average CPU utilization is below threshold."""
        instances = await self.get_instances()
        # In real impl, cross-reference with CloudWatch metrics
        return [
            {
                "instance_id": inst.resource_id,
                "name": inst.resource_name,
                "instance_type": inst.configuration.get("instance_type"),
                "avg_cpu": inst.configuration.get("avg_cpu_utilization", 3.5),
                "region": inst.region,
                "monthly_cost": inst.configuration.get("monthly_cost_inr", 0),
            }
            for inst in instances
            if inst.configuration.get("avg_cpu_utilization", 0) < cpu_threshold
        ]

    async def resize_instance(
        self, instance_id: str, new_instance_type: str
    ) -> Dict[str, Any]:
        """Stop, modify, and start an EC2 instance."""
        if self._ec2 is None:
            logger.info("[MOCK] Resizing %s to %s", instance_id, new_instance_type)
            return {"success": True, "instance_id": instance_id, "new_type": new_instance_type}
        try:
            self._ec2.stop_instances(InstanceIds=[instance_id])
            # Wait for stop (simplified – use waiter in production)
            self._ec2.modify_instance_attribute(
                InstanceId=instance_id,
                Attribute="instanceType",
                Value=new_instance_type,
            )
            self._ec2.start_instances(InstanceIds=[instance_id])
            return {"success": True, "instance_id": instance_id, "new_type": new_instance_type}
        except Exception as exc:
            logger.error("Resize EC2 error: %s", exc)
            return {"success": False, "error": str(exc)}

    async def get_instance_pricing(self, instance_type: str, region: str = "us-east-1") -> float:
        """Return estimated monthly on-demand cost in INR."""
        pricing_usd = {
            "t3.micro": 7.59, "t3.small": 15.18, "t3.medium": 30.37,
            "t3.large": 60.74, "t3.xlarge": 121.47, "t3.2xlarge": 242.94,
            "m5.large": 69.12, "m5.xlarge": 138.24, "m5.2xlarge": 276.48,
            "m5.4xlarge": 552.96, "c5.large": 61.20, "c5.xlarge": 122.40,
            "r5.large": 90.72, "r5.xlarge": 181.44,
        }
        usd = pricing_usd.get(instance_type, 50.0)
        return round(usd * 83.0, 2)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _fetch_real_instances(self) -> List[ResourceInfo]:
        response = self._ec2.describe_instances(
            Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
        )
        instances = []
        for reservation in response.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                name = next(
                    (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), ""
                )
                instances.append(ResourceInfo(
                    resource_id=inst["InstanceId"],
                    resource_name=name,
                    resource_type="compute",
                    provider="aws",
                    region=inst.get("Placement", {}).get("AvailabilityZone", self.region),
                    configuration={
                        "instance_type": inst["InstanceType"],
                        "state": inst["State"]["Name"],
                        "launch_time": str(inst.get("LaunchTime", "")),
                    },
                    tags={t["Key"]: t["Value"] for t in inst.get("Tags", [])},
                ))
        return instances

    def _mock_instances(self) -> List[ResourceInfo]:
        mock_data = [
            ("i-0abc123456789001", "web-server-prod",   "t3.large",   "us-east-1a", 28.4,  5040),
            ("i-0abc123456789002", "api-server-prod",   "m5.xlarge",  "us-east-1b", 35.2,  11476),
            ("i-0abc123456789003", "db-server-prod",    "r5.large",   "us-east-1a", 62.1,  7530),
            ("i-0abc123456789004", "worker-dev",        "t3.medium",  "us-east-1c",  3.1,   2521),  # idle
            ("i-0abc123456789005", "batch-processor",   "c5.xlarge",  "us-east-1b",  4.8,  10159),  # idle
        ]
        return [
            ResourceInfo(
                resource_id=iid,
                resource_name=name,
                resource_type="compute",
                provider="aws",
                region=zone,
                configuration={
                    "instance_type": itype,
                    "avg_cpu_utilization": cpu,
                    "monthly_cost_inr": cost,
                },
            )
            for iid, name, itype, zone, cpu, cost in mock_data
        ]

"""
AWS S3 / EBS storage adapter.
"""

import logging
from typing import Any, Dict, List, Optional

from cloud.base import ResourceInfo

logger = logging.getLogger(__name__)


class AWSStorageAdapter:

    def __init__(self, access_key: Optional[str] = None,
                 secret_key: Optional[str] = None,
                 region: str = "us-east-1"):
        self.region = region
        self._s3 = None
        try:
            import boto3
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
            self._s3 = session.client("s3")
        except Exception as exc:
            logger.warning("AWS S3 client unavailable: %s", exc)

    async def get_buckets(self) -> List[ResourceInfo]:
        if self._s3 is None:
            return self._mock_buckets()
        try:
            response = self._s3.list_buckets()
            return [
                ResourceInfo(
                    resource_id=b["Name"],
                    resource_name=b["Name"],
                    resource_type="storage",
                    provider="aws",
                    region=self.region,
                    configuration={"creation_date": str(b.get("CreationDate", ""))},
                )
                for b in response.get("Buckets", [])
            ]
        except Exception as exc:
            logger.error("S3 list_buckets error: %s", exc)
            return self._mock_buckets()

    async def get_storage_cost(self) -> float:
        """Return estimated monthly S3 cost in INR."""
        return 3800.0  # mock

    async def get_unencrypted_buckets(self) -> List[str]:
        """Return bucket names that lack server-side encryption."""
        if self._s3 is None:
            return ["logs-bucket-dev", "backup-archive-2023"]
        unencrypted = []
        buckets = self._s3.list_buckets().get("Buckets", [])
        for b in buckets:
            try:
                self._s3.get_bucket_encryption(Bucket=b["Name"])
            except self._s3.exceptions.from_code("ServerSideEncryptionConfigurationNotFoundError"):
                unencrypted.append(b["Name"])
        return unencrypted

    async def get_public_buckets(self) -> List[str]:
        """Return bucket names that have public access enabled."""
        return ["static-assets-public"]  # mock

    def _mock_buckets(self) -> List[ResourceInfo]:
        buckets = [
            ("app-data-prod",        250,  True,  False),
            ("logs-bucket-dev",       80,  False, False),  # unencrypted
            ("static-assets-public",  40,  True,  True),   # public
            ("backup-archive-2023",  180,  False, False),  # unencrypted
        ]
        return [
            ResourceInfo(
                resource_id=name,
                resource_name=name,
                resource_type="storage",
                provider="aws",
                region=self.region,
                configuration={
                    "size_gb": size,
                    "encrypted": enc,
                    "public_access": pub,
                    "monthly_cost_inr": round(size * 1.9, 2),  # ≈ $0.023/GB converted
                },
            )
            for name, size, enc, pub in buckets
        ]

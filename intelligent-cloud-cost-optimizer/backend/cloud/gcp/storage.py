"""GCP Cloud Storage adapter."""

import logging
from typing import Any, Dict, List, Optional
from cloud.base import ResourceInfo

logger = logging.getLogger(__name__)


class GCPStorageAdapter:

    def __init__(self, project_id: Optional[str] = None,
                 credentials_file: Optional[str] = None, **kwargs):
        self.project_id = project_id
        self._client = None
        try:
            from google.cloud import storage
            if credentials_file:
                self._client = storage.Client.from_service_account_json(credentials_file)
            elif project_id:
                self._client = storage.Client(project=project_id)
        except Exception as exc:
            logger.warning("GCP Storage SDK unavailable: %s", exc)

    async def get_buckets(self) -> List[ResourceInfo]:
        if self._client is None:
            return self._mock_buckets()
        try:
            return [
                ResourceInfo(
                    resource_id=b.name,
                    resource_name=b.name,
                    resource_type="storage",
                    provider="gcp",
                    region=b.location or "us",
                    configuration={"storage_class": b.storage_class, "uniform_access": b.iam_configuration.uniform_bucket_level_access_enabled},
                )
                for b in self._client.list_buckets()
            ]
        except Exception as exc:
            logger.error("GCP Storage list error: %s", exc)
            return self._mock_buckets()

    def _mock_buckets(self) -> List[ResourceInfo]:
        data = [
            ("prod-app-data",     "STANDARD",   200, True,  False),
            ("dev-logs",          "NEARLINE",    80, False, False),
            ("public-assets",     "STANDARD",    40, True,  True),
            ("backup-archive",    "COLDLINE",   150, True,  False),
        ]
        return [
            ResourceInfo(
                resource_id=name,
                resource_name=name,
                resource_type="storage",
                provider="gcp",
                region="us-central1",
                configuration={
                    "storage_class": cls,
                    "size_gb": size,
                    "uniform_access": uniform,
                    "public_access": pub,
                    "monthly_cost_inr": round(size * 1.66, 2),
                },
            )
            for name, cls, size, uniform, pub in data
        ]

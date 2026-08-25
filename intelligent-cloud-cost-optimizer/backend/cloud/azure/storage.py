"""Azure Blob Storage adapter."""

import logging
from typing import Any, Dict, List, Optional
from cloud.base import ResourceInfo

logger = logging.getLogger(__name__)


class AzureStorageAdapter:

    def __init__(self, subscription_id: Optional[str] = None,
                 tenant_id: Optional[str] = None,
                 client_id: Optional[str] = None,
                 client_secret: Optional[str] = None):
        self.subscription_id = subscription_id
        self._client = None
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.storage import StorageManagementClient
            if all([subscription_id, tenant_id, client_id, client_secret]):
                cred = ClientSecretCredential(tenant_id, client_id, client_secret)
                self._client = StorageManagementClient(cred, subscription_id)
        except Exception as exc:
            logger.warning("Azure Storage SDK unavailable: %s", exc)

    async def get_storage_accounts(self) -> List[ResourceInfo]:
        if self._client is None:
            return self._mock_storage_accounts()
        try:
            accounts = list(self._client.storage_accounts.list())
            return [
                ResourceInfo(
                    resource_id=acc.id,
                    resource_name=acc.name,
                    resource_type="storage",
                    provider="azure",
                    region=acc.location,
                    configuration={
                        "kind": acc.kind,
                        "sku": acc.sku.name if acc.sku else None,
                        "https_only": acc.enable_https_traffic_only,
                    },
                )
                for acc in accounts
            ]
        except Exception as exc:
            logger.error("Azure Storage list error: %s", exc)
            return self._mock_storage_accounts()

    def _mock_storage_accounts(self) -> List[ResourceInfo]:
        data = [
            ("prodstorageacct01",  True,  "Standard_GRS",  500),
            ("devstorageacct01",   False, "Standard_LRS",   50),   # http allowed
            ("backupstorageacct",  True,  "Standard_RAGRS", 300),
        ]
        return [
            ResourceInfo(
                resource_id=f"/subscriptions/xxx/resourceGroups/rg-prod/providers/Microsoft.Storage/storageAccounts/{name}",
                resource_name=name,
                resource_type="storage",
                provider="azure",
                region="eastus",
                configuration={
                    "https_only": https,
                    "sku": sku,
                    "size_gb": size,
                    "monthly_cost_inr": round(size * 1.5, 2),
                },
            )
            for name, https, sku, size in data
        ]

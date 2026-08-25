"""Azure Virtual Machine compute adapter."""

import logging
from typing import Any, Dict, List, Optional
from cloud.base import ResourceInfo

logger = logging.getLogger(__name__)


class AzureComputeAdapter:

    def __init__(self, subscription_id: Optional[str] = None,
                 tenant_id: Optional[str] = None,
                 client_id: Optional[str] = None,
                 client_secret: Optional[str] = None):
        self.subscription_id = subscription_id
        self._client = None
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.compute import ComputeManagementClient
            if all([subscription_id, tenant_id, client_id, client_secret]):
                cred = ClientSecretCredential(tenant_id, client_id, client_secret)
                self._client = ComputeManagementClient(cred, subscription_id)
        except Exception as exc:
            logger.warning("Azure Compute SDK unavailable: %s", exc)

    async def get_instances(self) -> List[ResourceInfo]:
        if self._client is None:
            return self._mock_instances()
        try:
            vms = list(self._client.virtual_machines.list_all())
            return [
                ResourceInfo(
                    resource_id=vm.id,
                    resource_name=vm.name,
                    resource_type="compute",
                    provider="azure",
                    region=vm.location,
                    configuration={"vm_size": vm.hardware_profile.vm_size},
                )
                for vm in vms
            ]
        except Exception as exc:
            logger.error("Azure VM list error: %s", exc)
            return self._mock_instances()

    async def resize_vm(self, resource_group: str, vm_name: str, new_size: str) -> Dict[str, Any]:
        if self._client is None:
            logger.info("[MOCK] Resize Azure VM %s to %s", vm_name, new_size)
            return {"success": True, "vm_name": vm_name, "new_size": new_size}
        try:
            from azure.mgmt.compute.models import VirtualMachineUpdate, HardwareProfile
            update = VirtualMachineUpdate(hardware_profile=HardwareProfile(vm_size=new_size))
            poller = self._client.virtual_machines.begin_update(resource_group, vm_name, update)
            poller.result()
            return {"success": True, "vm_name": vm_name, "new_size": new_size}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def get_vm_pricing(self, vm_size: str) -> float:
        pricing_usd = {
            "Standard_B1s": 7.59, "Standard_B2s": 30.37, "Standard_B4ms": 121.47,
            "Standard_D2s_v3": 69.12, "Standard_D4s_v3": 138.24,
            "Standard_E2s_v3": 90.72, "Standard_F2s_v2": 61.20,
        }
        return round(pricing_usd.get(vm_size, 50.0) * 83.0, 2)

    def _mock_instances(self) -> List[ResourceInfo]:
        data = [
            ("vm-web-prod",    "Standard_D2s_v3",  "eastus",    29.1,  5736),
            ("vm-api-prod",    "Standard_D4s_v3",  "eastus",    38.5,  11472),
            ("vm-db-prod",     "Standard_E2s_v3",  "eastus",    55.0,   7530),
            ("vm-dev-worker",  "Standard_B2s",     "eastus2",    4.2,   2521),
        ]
        return [
            ResourceInfo(
                resource_id=f"/subscriptions/xxx/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/{name}",
                resource_name=name,
                resource_type="compute",
                provider="azure",
                region=region,
                configuration={"vm_size": size, "avg_cpu_utilization": cpu, "monthly_cost_inr": cost},
            )
            for name, size, region, cpu, cost in data
        ]

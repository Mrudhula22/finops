"""Azure cloud adapter package."""
from .cost import AzureCostAdapter
from .compute import AzureComputeAdapter
from .storage import AzureStorageAdapter
from .monitoring import AzureMonitoringAdapter
from .security import AzureSecurityAdapter

__all__ = [
    "AzureCostAdapter",
    "AzureComputeAdapter",
    "AzureStorageAdapter",
    "AzureMonitoringAdapter",
    "AzureSecurityAdapter",
]

"""AWS cloud adapter package."""
from .cost import AWSCostAdapter
from .compute import AWSComputeAdapter
from .storage import AWSStorageAdapter
from .monitoring import AWSMonitoringAdapter
from .security import AWSSecurityAdapter

__all__ = [
    "AWSCostAdapter",
    "AWSComputeAdapter",
    "AWSStorageAdapter",
    "AWSMonitoringAdapter",
    "AWSSecurityAdapter",
]

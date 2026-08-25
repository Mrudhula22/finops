"""
Base cloud adapter interface.
Every provider adapter inherits from these abstract base classes
so the optimization engine can treat them uniformly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ResourceInfo:
    resource_id: str
    resource_name: str
    resource_type: str          # compute | storage | database | network
    provider: str
    region: str
    configuration: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    is_active: bool = True


@dataclass
class CostEntry:
    provider: str
    service: str
    amount: float               # INR
    currency: str = "INR"
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    resource_id: Optional[str] = None
    cost_type: str = "OnDemand"


@dataclass
class UsageEntry:
    resource_id: str
    metric_name: str
    metric_value: float
    unit: str
    timestamp: datetime


@dataclass
class SecurityFinding:
    check_id: str
    title: str
    severity: str               # critical | high | medium | low
    resource_id: str
    description: str
    remediation: str
    passed: bool


class BaseCloudAdapter(ABC):
    """Abstract interface every cloud adapter must implement."""

    @abstractmethod
    async def get_cost_summary(
        self, start_date: datetime, end_date: datetime
    ) -> List[CostEntry]:
        """Return line-item costs for the given period."""
        ...

    @abstractmethod
    async def get_resources(self) -> List[ResourceInfo]:
        """List all active resources in the account."""
        ...

    @abstractmethod
    async def get_usage_metrics(
        self, resource_id: str, start_date: datetime, end_date: datetime
    ) -> List[UsageEntry]:
        """Return time-series usage metrics for a resource."""
        ...

    @abstractmethod
    async def get_security_findings(self) -> List[SecurityFinding]:
        """Run security checks and return findings."""
        ...

    @abstractmethod
    async def resize_resource(self, resource_id: str, new_config: Dict[str, Any]) -> bool:
        """Resize / reconfigure a resource."""
        ...

    @abstractmethod
    async def get_pricing(self, resource_type: str, config: Dict[str, Any]) -> float:
        """Return estimated monthly cost in INR for a given configuration."""
        ...

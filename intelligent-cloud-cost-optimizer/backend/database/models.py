"""Beanie ODM Document Models for MongoDB (Beanie 2.x compatible)."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import pymongo
from beanie import Document
from pydantic import Field, EmailStr


class CloudProvider(str, Enum):
    AWS="aws"; AZURE="azure"; GCP="gcp"

class ResourceType(str, Enum):
    COMPUTE="compute"; STORAGE="storage"; DATABASE="database"; NETWORK="network"; OTHER="other"

class RecommendationStatus(str, Enum):
    PENDING="pending"; APPROVED="approved"; REJECTED="rejected"
    EXECUTING="executing"; COMPLETED="completed"; FAILED="failed"; ROLLED_BACK="rolled_back"

class ActionStatus(str, Enum):
    PENDING="pending"; RUNNING="running"; SUCCESS="success"; FAILED="failed"; ROLLED_BACK="rolled_back"

class RiskLevel(str, Enum):
    LOW="low"; MEDIUM="medium"; HIGH="high"; CRITICAL="critical"


class User(Document):
    email: EmailStr
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"
        indexes = [pymongo.IndexModel([("email", pymongo.ASCENDING)], unique=True)]


class CloudAccount(Document):
    user_id: str
    provider: CloudProvider
    account_name: str
    account_id: Optional[str] = None
    is_active: bool = True
    monthly_budget: float = 50000.0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "cloud_accounts"


class CloudResource(Document):
    account_id: str
    provider: CloudProvider
    resource_type: ResourceType
    resource_id: str
    resource_name: Optional[str] = None
    region: Optional[str] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)
    tags: Dict[str, str] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "cloud_resources"


class CostRecord(Document):
    resource_id: str
    provider: CloudProvider
    service: Optional[str] = None
    amount: float
    currency: str = "INR"
    period_start: datetime
    period_end: datetime
    cost_type: str = "OnDemand"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "cost_records"
        indexes = [pymongo.IndexModel([("provider", pymongo.ASCENDING), ("period_start", pymongo.DESCENDING)])]


class UsageMetric(Document):
    resource_id: str
    metric_name: str
    metric_value: float
    unit: str
    timestamp: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "usage_metrics"


class ForecastResult(Document):
    account_id: str
    provider: CloudProvider
    model_name: Optional[str] = None
    predicted_cost: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    budget_overrun: Optional[float] = None
    confidence: Optional[float] = None
    forecast_data: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "forecast_results"


class Anomaly(Document):
    resource_id: str
    anomaly_type: Optional[str] = None
    severity: RiskLevel
    description: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    is_resolved: bool = False

    class Settings:
        name = "anomalies"


class OptimizationRecommendation(Document):
    account_id: str = "default"
    resource_id: Optional[str] = None
    recommendation_type: Optional[str] = None
    current_provider: Optional[CloudProvider] = None
    recommended_provider: Optional[CloudProvider] = None
    current_config: Dict[str, Any] = Field(default_factory=dict)
    recommended_config: Dict[str, Any] = Field(default_factory=dict)
    current_cost: Optional[float] = None
    predicted_cost: Optional[float] = None
    estimated_saving: Optional[float] = None
    saving_percentage: Optional[float] = None
    security_score: Optional[float] = None
    risk_score: Optional[float] = None
    confidence_score: Optional[float] = None
    reason: Optional[str] = None
    explanation: Dict[str, Any] = Field(default_factory=dict)
    status: RecommendationStatus = RecommendationStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "optimization_recommendations"
        indexes = [pymongo.IndexModel([("status", pymongo.ASCENDING)])]


class SecurityAssessment(Document):
    resource_id: str
    provider: CloudProvider
    overall_score: float = 0.0
    iam_score: float = 0.0
    encryption_score: float = 0.0
    network_score: float = 0.0
    compliance_score: float = 0.0
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    passed_checks: int = 0
    failed_checks: int = 0
    assessed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "security_assessments"


class RiskScore(Document):
    recommendation_id: str
    risk_level: RiskLevel
    overall_score: float = 0.0
    factors: List[str] = Field(default_factory=list)
    mitigation: List[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "risk_scores"


class ExecutionAction(Document):
    recommendation_id: str
    action_type: str
    provider: CloudProvider
    resource_id: str
    status: ActionStatus = ActionStatus.PENDING
    executed_by: str = "system"
    result: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "execution_actions"


class RollbackRecord(Document):
    action_id: str
    reason: Optional[str] = None
    rollback_status: ActionStatus = ActionStatus.PENDING
    initiated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    class Settings:
        name = "rollback_records"


class AgentFeedback(Document):
    recommendation_id: str
    rating: Optional[int] = None
    comments: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "agent_feedback"


class AuditLog(Document):
    user_id: Optional[str] = None
    action: str
    resource: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "audit_logs"
        indexes = [pymongo.IndexModel([("created_at", pymongo.DESCENDING)])]

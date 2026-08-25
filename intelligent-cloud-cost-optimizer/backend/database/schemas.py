"""Pydantic request/response schemas (MongoDB version)."""
from pydantic import BaseModel, EmailStr, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum


class CloudProvider(str, Enum):
    AWS="aws"; AZURE="azure"; GCP="gcp"

class RecommendationStatus(str, Enum):
    PENDING="pending"; APPROVED="approved"; REJECTED="rejected"
    EXECUTING="executing"; COMPLETED="completed"; FAILED="failed"; ROLLED_BACK="rolled_back"

class RiskLevel(str, Enum):
    LOW="low"; MEDIUM="medium"; HIGH="high"; CRITICAL="critical"

class _Base(BaseModel):
    model_config = {"from_attributes": True}

class UserCreate(_Base):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None

class UserRead(_Base):
    id: str
    email: EmailStr
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime

class Token(_Base):
    access_token: str
    token_type: str = "bearer"
    user: UserRead

class LoginRequest(_Base):
    email: EmailStr
    password: str

class UserUpdate(_Base):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None

class ForecastRequest(_Base):
    provider: Optional[CloudProvider] = None
    model: str = "ensemble"
    periods: int = Field(30, ge=7, le=365)

class ForecastPoint(_Base):
    date: str; predicted: float; lower: float; upper: float

class RecommendationRead(_Base):
    id: str
    recommendation_type: Optional[str]
    current_provider: Optional[CloudProvider]
    recommended_provider: Optional[CloudProvider]
    current_cost: Optional[float]
    estimated_saving: Optional[float]
    saving_percentage: Optional[float]
    security_score: Optional[float]
    confidence_score: Optional[float]
    reason: Optional[str]
    status: RecommendationStatus
    created_at: datetime

class ExecutionRequest(_Base):
    recommendation_id: str
    mode: str = "recommendation"

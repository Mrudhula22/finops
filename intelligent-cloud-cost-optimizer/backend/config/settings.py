"""
Application Settings
Loads all configuration from environment variables via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────
    APP_NAME: str = "Intelligent Cloud Cost Optimizer"
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    DEBUG: bool = True
    VERSION: str = "1.0.0"

    # ── Database — MongoDB ────────────────────────────────
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "cloudoptimizer"
    REDIS_URL: str = "redis://localhost:6379"

    # ── JWT ──────────────────────────────────────────────
    JWT_SECRET: str = "jwt-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # ── AWS ──────────────────────────────────────────────
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: str = "us-east-1"
    AWS_ACCOUNT_ID: Optional[str] = None

    # ── Azure ────────────────────────────────────────────
    AZURE_SUBSCRIPTION_ID: Optional[str] = None
    AZURE_TENANT_ID: Optional[str] = None
    AZURE_CLIENT_ID: Optional[str] = None
    AZURE_CLIENT_SECRET: Optional[str] = None

    # ── GCP ──────────────────────────────────────────────
    GCP_PROJECT_ID: Optional[str] = None
    GCP_CREDENTIALS_FILE: Optional[str] = None
    GCP_REGION: str = "us-central1"

    # ── OpenAI ───────────────────────────────────────────
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"

    # ── Email ────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    # ── Budget ───────────────────────────────────────────
    DEFAULT_MONTHLY_BUDGET: float = 50000.0   # INR
    BUDGET_ALERT_THRESHOLD: float = 0.85

    # ── Agent ────────────────────────────────────────────
    AGENT_AUTONOMOUS_MODE: bool = False
    AGENT_MAX_RETRIES: int = 3
    AGENT_TIMEOUT_SECONDS: int = 300

    # ── CORS ─────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = {"env_file": "../.env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

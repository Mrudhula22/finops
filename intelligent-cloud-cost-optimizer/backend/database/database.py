"""
MongoDB connection — Motor async + Beanie ODM.
If MongoDB is not running locally, the app still starts and uses
mock/in-memory data served by the cloud adapters.
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import settings

logger = logging.getLogger(__name__)

_client = None
_db_ready = False


def get_client():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=3000,   # fail fast if Mongo not available
        )
    return _client


def get_database():
    return get_client()[settings.MONGODB_DB]


async def init_db():
    global _db_ready
    try:
        from beanie import init_beanie
        from database.models import (
            User, CloudAccount, CloudResource, CostRecord, UsageMetric,
            ForecastResult, Anomaly, OptimizationRecommendation,
            SecurityAssessment, RiskScore, ExecutionAction,
            RollbackRecord, AgentFeedback, AuditLog,
        )
        client = get_client()
        # Ping to check connection
        await client.admin.command("ping")
        database = client[settings.MONGODB_DB]
        await init_beanie(
            database=database,
            document_models=[
                User, CloudAccount, CloudResource, CostRecord, UsageMetric,
                ForecastResult, Anomaly, OptimizationRecommendation,
                SecurityAssessment, RiskScore, ExecutionAction,
                RollbackRecord, AgentFeedback, AuditLog,
            ],
        )
        _db_ready = True
        logger.info("✅ MongoDB connected: %s / %s", settings.MONGODB_URL, settings.MONGODB_DB)
    except Exception as e:
        _db_ready = False
        logger.warning("⚠️  MongoDB not available (%s). Running in mock/demo mode.", e)


def is_db_ready() -> bool:
    return _db_ready


async def get_db():
    yield get_database()

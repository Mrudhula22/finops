"""
Intelligent Multi-Cloud Cost Optimizer — FastAPI Entry Point
MongoDB / Beanie version
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import settings
from database.database import init_db

# ── API routers ──────────────────────────────────────────────────────────────
from api.auth            import router as auth_router
from api.costs           import router as costs_router
from api.forecast        import router as forecast_router
from api.recommendations import router as recommendations_router
from api.multicloud      import router as multicloud_router
from api.execution       import router as execution_router
from api.dashboard       import router as dashboard_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — connecting to MongoDB...")
    await init_db()
    logger.info("MongoDB ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Intelligent Multi-Cloud Cost Optimizer",
    version="1.0.0",
    description="Autonomous & Explainable AI for AWS / Azure / GCP cost optimization.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,            prefix="/api/auth",            tags=["Auth"])
app.include_router(dashboard_router,       prefix="/api/dashboard",       tags=["Dashboard"])
app.include_router(costs_router,           prefix="/api/costs",           tags=["Costs"])
app.include_router(forecast_router,        prefix="/api/forecast",        tags=["Forecast"])
app.include_router(recommendations_router, prefix="/api/recommendations", tags=["Recommendations"])
app.include_router(multicloud_router,      prefix="/api/multicloud",      tags=["Multi-Cloud"])
app.include_router(execution_router,       prefix="/api/execution",       tags=["Execution"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/", tags=["Root"])
async def root():
    return {"message": "AI Cloud Cost Optimizer API", "docs": "/docs"}

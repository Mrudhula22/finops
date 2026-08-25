"""
Forecast API — /api/forecast
  POST /predict         - run forecast with chosen model
  GET  /compare         - compare all models side-by-side
  GET  /budget-risk     - budget overrun probability
  POST /experiments     - run full model comparison (research use)
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.deps import get_current_user
from cloud.collector import MultiCloudCollector
from database.models import User

logger = logging.getLogger(__name__)
router = APIRouter()


class ForecastRequest(BaseModel):
    provider: Optional[str] = None     # aws | azure | gcp | None (all)
    model: str = "ensemble"            # arima | prophet | xgboost | ensemble
    periods: int = Field(30, ge=7, le=365)


@router.post("/predict")
async def predict_costs(
    payload: ForecastRequest,
    current_user: User = Depends(get_current_user),
):
    """Run cost forecast for a provider using the chosen model."""
    from ml.forecasting.arima_model import ARIMAForecaster
    from ml.forecasting.prophet_model import ProphetForecaster
    from ml.forecasting.xgboost_model import XGBoostForecaster
    from ml.forecasting.ensemble import EnsembleForecaster

    model_map = {
        "arima":    ARIMAForecaster,
        "prophet":  ProphetForecaster,
        "xgboost":  XGBoostForecaster,
        "ensemble": EnsembleForecaster,
    }
    ForecasterClass = model_map.get(payload.model, EnsembleForecaster)

    collector = MultiCloudCollector()
    history   = await collector.get_historical_costs(months=12)

    results = {}
    providers = [payload.provider] if payload.provider else ["aws", "azure", "gcp"]

    for prov in providers:
        hist = history.get(prov, [])
        if not hist:
            continue
        dates  = [h["date"] for h in hist]
        values = [h["cost"] for h in hist]

        fc = ForecasterClass(provider=prov)
        fc.fit(dates, values)
        result = fc.predict(periods=payload.periods)

        results[prov] = {
            "model":                result.model_name,
            "current_monthly_cost": result.current_monthly_cost,
            "predicted_next_month": result.predicted_next_month,
            "lower_bound":          result.lower_bound,
            "upper_bound":          result.upper_bound,
            "confidence":           result.confidence,
            "budget_overrun":       result.budget_overrun,
            "overrun_risk":         result.overrun_risk,
            "forecast_points":      [p.__dict__ for p in result.forecast_points],
            "metrics":              result.metrics,
        }

    # Total across all providers
    total_predicted = sum(r["predicted_next_month"] for r in results.values())
    from config.settings import settings
    budget = settings.DEFAULT_MONTHLY_BUDGET

    return {
        "forecasts":        results,
        "total_predicted":  round(total_predicted, 2),
        "monthly_budget":   budget,
        "total_overrun":    round(max(0, total_predicted - budget), 2),
        "overall_risk":     "high" if total_predicted > budget else
                            "medium" if total_predicted > budget * 0.85 else "low",
        "model_used":       payload.model,
        "generated_at":     datetime.utcnow().isoformat(),
    }


@router.get("/compare")
async def compare_models(
    provider: str = Query("aws", description="Provider to compare models on"),
    current_user: User = Depends(get_current_user),
):
    """Compare ARIMA, Prophet, XGBoost, and Ensemble side-by-side."""
    from ml.forecasting.arima_model import ARIMAForecaster
    from ml.forecasting.prophet_model import ProphetForecaster
    from ml.forecasting.xgboost_model import XGBoostForecaster
    from ml.forecasting.ensemble import EnsembleForecaster
    from ml.evaluation.metrics import ModelEvaluator

    collector = MultiCloudCollector()
    history   = await collector.get_historical_costs(months=12)
    hist      = history.get(provider, [])

    if not hist:
        return {"error": f"No history for provider '{provider}'"}

    dates  = [h["date"] for h in hist]
    values = [h["cost"] for h in hist]

    forecasters = {
        "ARIMA":    ARIMAForecaster(provider),
        "Prophet":  ProphetForecaster(provider),
        "XGBoost":  XGBoostForecaster(provider),
        "Ensemble": EnsembleForecaster(provider),
    }

    evaluator = ModelEvaluator(n_splits=3, test_size=1)
    comparison = evaluator.compare_models(forecasters, dates, values)

    # Add sample 30-day forecast for each model
    sample = {}
    for name, fc in forecasters.items():
        try:
            fc.fit(dates, values)
            res = fc.predict(30)
            sample[name] = {
                "predicted_next_month": res.predicted_next_month,
                "confidence":           res.confidence,
                "metrics":              res.metrics,
            }
        except Exception as e:
            sample[name] = {"error": str(e)}

    return {
        "provider":     provider,
        "comparison":   comparison,
        "forecasts":    sample,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/budget-risk")
async def budget_risk(
    current_user: User = Depends(get_current_user),
):
    """Probability of budget overrun next month."""
    from ml.forecasting.ensemble import EnsembleForecaster
    from config.settings import settings

    collector = MultiCloudCollector()
    history   = await collector.get_historical_costs(months=12)

    total_predicted = 0.0
    risks = {}
    for prov in ["aws", "azure", "gcp"]:
        hist = history.get(prov, [])
        if not hist:
            continue
        dates  = [h["date"] for h in hist]
        values = [h["cost"] for h in hist]
        fc = EnsembleForecaster(provider=prov)
        fc.fit(dates, values)
        res = fc.predict(30)
        total_predicted += res.predicted_next_month
        risks[prov] = {
            "predicted": res.predicted_next_month,
            "overrun":   res.budget_overrun,
            "risk":      res.overrun_risk,
        }

    budget  = settings.DEFAULT_MONTHLY_BUDGET
    overrun = max(0, total_predicted - budget)
    overall_risk = "high" if total_predicted > budget else \
                   "medium" if total_predicted > budget * 0.85 else "low"

    return {
        "monthly_budget":    budget,
        "total_predicted":   round(total_predicted, 2),
        "total_overrun":     round(overrun, 2),
        "overall_risk":      overall_risk,
        "per_provider":      risks,
        "generated_at":      datetime.utcnow().isoformat(),
    }


@router.post("/experiments")
async def run_experiments(
    provider: str = "aws",
    current_user: User = Depends(get_current_user),
):
    """Run full model comparison experiment (for research paper)."""
    from ml.evaluation.experiments import ExperimentRunner

    collector = MultiCloudCollector()
    history   = await collector.get_historical_costs(months=12)
    hist      = history.get(provider, [])

    if not hist:
        return {"error": f"No history for provider '{provider}'"}

    dates  = [h["date"] for h in hist]
    values = [h["cost"] for h in hist]

    runner  = ExperimentRunner()
    results = runner.run_all(dates, values, provider=provider)
    return results

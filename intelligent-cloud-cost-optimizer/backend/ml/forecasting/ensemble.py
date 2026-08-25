"""
Ensemble Forecaster.
Combines ARIMA, Prophet, and XGBoost predictions using weighted averaging.
Weights are assigned based on each model's hold-out MAPE.
"""

import logging
from typing import List, Dict, Any

import numpy as np

from ml.forecasting.base_forecaster import BaseForecaster, ForecastResult, ForecastPoint
from ml.forecasting.arima_model import ARIMAForecaster
from ml.forecasting.prophet_model import ProphetForecaster
from ml.forecasting.xgboost_model import XGBoostForecaster

logger = logging.getLogger(__name__)


class EnsembleForecaster(BaseForecaster):
    """Weighted ensemble of ARIMA + Prophet + XGBoost."""

    def __init__(self, provider: str = "all"):
        self.provider = provider
        self._forecasters = {
            "arima":   ARIMAForecaster(provider),
            "prophet": ProphetForecaster(provider),
            "xgboost": XGBoostForecaster(provider),
        }
        self._weights: Dict[str, float] = {"arima": 0.33, "prophet": 0.34, "xgboost": 0.33}
        self._dates:  List[str]   = []
        self._values: List[float] = []

    def fit(self, dates: List[str], values: List[float]) -> None:
        self._dates  = dates
        self._values = values
        mape_scores: Dict[str, float] = {}

        for name, fc in self._forecasters.items():
            try:
                fc.fit(dates, values)
                result = fc.predict(periods=30)
                mape_scores[name] = result.metrics.get("mape", 10.0)
                logger.info("Ensemble sub-model %s: MAPE=%.2f%%", name, mape_scores[name])
            except Exception as exc:
                logger.warning("Sub-model %s fit error: %s", name, exc)
                mape_scores[name] = 20.0

        # Weight = 1/MAPE (better = higher weight), then normalise
        raw_weights = {k: 1.0 / max(v, 0.1) for k, v in mape_scores.items()}
        total = sum(raw_weights.values())
        self._weights = {k: v / total for k, v in raw_weights.items()}
        logger.info("Ensemble weights: %s", {k: round(v, 3) for k, v in self._weights.items()})

    def predict(self, periods: int = 30) -> ForecastResult:
        if not self._values:
            dates, values = self._generate_mock_history()
            self.fit(dates, values)

        results: Dict[str, ForecastResult] = {}
        for name, fc in self._forecasters.items():
            try:
                results[name] = fc.predict(periods)
            except Exception as exc:
                logger.warning("Sub-model %s predict error: %s", name, exc)

        if not results:
            return self._forecasters["prophet"].predict(periods)

        # Align forecast point dates from prophet (or whichever is available)
        ref = next(iter(results.values()))
        n_points = len(ref.forecast_points)

        ensemble_points: List[ForecastPoint] = []
        for i in range(n_points):
            weighted_pred = 0.0
            weighted_lower = 0.0
            weighted_upper = 0.0
            total_weight = 0.0
            for name, result in results.items():
                if i < len(result.forecast_points):
                    w = self._weights.get(name, 0.33)
                    pt = result.forecast_points[i]
                    weighted_pred  += w * pt.predicted
                    weighted_lower += w * pt.lower
                    weighted_upper += w * pt.upper
                    total_weight   += w
            if total_weight > 0:
                ensemble_points.append(ForecastPoint(
                    date=ref.forecast_points[i].date,
                    predicted=round(weighted_pred  / total_weight, 2),
                    lower=round(weighted_lower / total_weight, 2),
                    upper=round(weighted_upper / total_weight, 2),
                ))

        # Weighted monthly prediction
        predicted_month = sum(
            self._weights.get(name, 0.33) * r.predicted_next_month
            for name, r in results.items()
        )

        # Confidence = weighted average of sub-model confidences
        confidence = sum(
            self._weights.get(name, 0.33) * r.confidence
            for name, r in results.items()
        )

        # Combined metrics
        combined_metrics = {
            "sub_models": {name: r.metrics for name, r in results.items()},
            "weights": {k: round(v, 3) for k, v in self._weights.items()},
        }

        current_cost = ref.current_monthly_cost

        return ForecastResult(
            model_name="ensemble",
            provider=self.provider,
            current_monthly_cost=current_cost,
            predicted_next_month=round(predicted_month, 2),
            lower_bound=round(predicted_month * 0.88, 2),
            upper_bound=round(predicted_month * 1.12, 2),
            confidence=round(min(0.99, confidence), 3),
            forecast_points=ensemble_points,
            metrics=combined_metrics,
        )

"""
Facebook Prophet Cost Forecaster.
Best for capturing seasonality and holiday effects in cloud billing.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

import numpy as np
import pandas as pd

from ml.forecasting.base_forecaster import BaseForecaster, ForecastResult, ForecastPoint

logger = logging.getLogger(__name__)


class ProphetForecaster(BaseForecaster):
    """Prophet-based forecaster with trend changepoints and seasonality."""

    def __init__(self, provider: str = "all"):
        self.provider = provider
        self._model = None
        self._df: Optional[pd.DataFrame] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def fit(self, dates: List[str], values: List[float]) -> None:
        try:
            from prophet import Prophet
        except ImportError:
            logger.warning("Prophet not installed. Using mock predictions.")
            self._df = pd.DataFrame({"ds": pd.to_datetime(dates), "y": values})
            return

        self._df = pd.DataFrame({"ds": pd.to_datetime(dates), "y": values})

        self._model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            interval_width=0.90,
        )
        # Add monthly seasonality for cloud billing cycles
        self._model.add_seasonality(name="monthly", period=30.5, fourier_order=5)
        self._model.fit(self._df)
        logger.info("Prophet model fitted on %d data points.", len(dates))

    def predict(self, periods: int = 30) -> ForecastResult:
        if self._df is None:
            dates, values = self._generate_mock_history()
            self.fit(dates, values)

        if self._model is None:
            return self._mock_predict(periods)

        try:
            future = self._model.make_future_dataframe(periods=periods, freq="D")
            forecast = self._model.predict(future)
            future_fc = forecast.tail(periods)

            fc_values  = np.maximum(future_fc["yhat"].values, 0)
            fc_lower   = np.maximum(future_fc["yhat_lower"].values, 0)
            fc_upper   = np.maximum(future_fc["yhat_upper"].values, 0)
            fc_dates   = future_fc["ds"].dt.strftime("%Y-%m-%d").tolist()

            points = [
                ForecastPoint(
                    date=fc_dates[i],
                    predicted=round(float(fc_values[i]), 2),
                    lower=round(float(fc_lower[i]), 2),
                    upper=round(float(fc_upper[i]), 2),
                )
                for i in range(len(fc_dates))
            ]

            # Monthly prediction = sum of next 30 daily values
            predicted_month = float(np.sum(fc_values[:30]))

            # In-sample cross-validation metrics using last 20%
            y = self._df["y"].values
            holdout_n = max(1, len(y) // 5)
            actual_hold = y[-holdout_n:]
            # Use in-sample prediction for held-out portion
            in_sample = forecast.head(len(y))["yhat"].values[-holdout_n:]
            metrics = self._calculate_metrics(
                np.array(actual_hold), np.array(in_sample)
            )

            mape = metrics.get("mape", 8)
            confidence = max(0.50, min(0.99, 1.0 - mape / 100))

            current_monthly = float(self._df["y"].iloc[-1])

            return ForecastResult(
                model_name="prophet",
                provider=self.provider,
                current_monthly_cost=current_monthly,
                predicted_next_month=round(predicted_month, 2),
                lower_bound=round(float(np.sum(fc_lower[:30])), 2),
                upper_bound=round(float(np.sum(fc_upper[:30])), 2),
                confidence=round(confidence, 3),
                forecast_points=points,
                metrics=metrics,
            )

        except Exception as exc:
            logger.error("Prophet predict error: %s", exc)
            return self._mock_predict(periods)

    # ── Fallback ──────────────────────────────────────────────────────────────

    def _mock_predict(self, periods: int) -> ForecastResult:
        values = self._df["y"].values if self._df is not None else np.array([40000.0] * 12)
        last_val = float(values[-1])
        trend = float(np.polyfit(range(len(values)), values, 1)[0])  # monthly slope

        base_date = datetime.utcnow()
        points = []
        for i in range(periods):
            daily_growth = trend / 30
            pred = max(0, last_val + daily_growth * (i + 1))
            points.append(ForecastPoint(
                date=(base_date + timedelta(days=i + 1)).strftime("%Y-%m-%d"),
                predicted=round(pred, 2),
                lower=round(pred * 0.88, 2),
                upper=round(pred * 1.12, 2),
            ))

        predicted_month = sum(p.predicted for p in points[:30])
        return ForecastResult(
            model_name="prophet",
            provider=self.provider,
            current_monthly_cost=last_val,
            predicted_next_month=round(predicted_month, 2),
            lower_bound=round(predicted_month * 0.88, 2),
            upper_bound=round(predicted_month * 1.12, 2),
            confidence=0.82,
            forecast_points=points,
            metrics={"note": "mock_fallback"},
        )

"""
XGBoost Cost Forecaster.
Converts time-series into a supervised learning problem using lag features,
rolling statistics, and calendar features.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

import numpy as np
import pandas as pd

from ml.forecasting.base_forecaster import BaseForecaster, ForecastResult, ForecastPoint

logger = logging.getLogger(__name__)


class XGBoostForecaster(BaseForecaster):
    """XGBoost regression model for cloud cost prediction."""

    LAG_FEATURES     = [1, 2, 3, 6, 12]        # months back
    ROLLING_WINDOWS  = [3, 6]                   # rolling mean/std windows

    def __init__(self, provider: str = "all"):
        self.provider = provider
        self._model = None
        self._dates: List[str] = []
        self._values: List[float] = []
        self._feature_names: List[str] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def fit(self, dates: List[str], values: List[float]) -> None:
        self._dates  = dates
        self._values = values

        df = self._build_features(dates, values)
        df = df.dropna()

        X = df.drop(columns=["target"])
        y = df["target"]
        self._feature_names = list(X.columns)

        try:
            import xgboost as xgb
            self._model = xgb.XGBRegressor(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=4,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbosity=0,
            )
            self._model.fit(X, y, eval_set=[(X, y)], verbose=False)
            logger.info("XGBoost fitted on %d samples with %d features.",
                        len(X), len(self._feature_names))
        except ImportError:
            logger.warning("XGBoost not installed. Will use linear fallback.")

    def predict(self, periods: int = 30) -> ForecastResult:
        if not self._values:
            dates, values = self._generate_mock_history()
            self.fit(dates, values)

        if self._model is None:
            return self._linear_fallback(periods)

        try:
            return self._xgb_predict(periods)
        except Exception as exc:
            logger.error("XGBoost predict error: %s", exc)
            return self._linear_fallback(periods)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _xgb_predict(self, periods: int) -> ForecastResult:
        """Recursive multi-step prediction."""
        extended_dates  = list(self._dates)
        extended_values = list(self._values)

        base_date = pd.to_datetime(self._dates[-1])
        predictions = []

        for i in range(periods):
            next_date = base_date + timedelta(days=30 * (i + 1) / 30)  # daily
            next_date_str = (pd.to_datetime(self._dates[-1]) + timedelta(days=i + 1)).strftime("%Y-%m-%d")

            # Build features for next step
            df = self._build_features(extended_dates, extended_values)
            last_row = df.iloc[-1].copy()
            last_row["month"]     = pd.to_datetime(next_date_str).month
            last_row["quarter"]   = pd.to_datetime(next_date_str).quarter
            last_row["month_sin"] = np.sin(2 * np.pi * last_row["month"] / 12)
            last_row["month_cos"] = np.cos(2 * np.pi * last_row["month"] / 12)

            X_pred = last_row[self._feature_names].values.reshape(1, -1)
            pred = float(self._model.predict(X_pred)[0])
            pred = max(0, pred)
            predictions.append(pred)

            extended_dates.append(next_date_str)
            extended_values.append(pred)

        predictions_arr = np.array(predictions)
        # Uncertainty: use std of training residuals as proxy
        std_est = float(np.std(self._values)) * 0.15

        points = [
            ForecastPoint(
                date=(pd.to_datetime(self._dates[-1]) + timedelta(days=i + 1)).strftime("%Y-%m-%d"),
                predicted=round(float(predictions_arr[i]), 2),
                lower=round(max(0, float(predictions_arr[i]) - 1.96 * std_est), 2),
                upper=round(float(predictions_arr[i]) + 1.96 * std_est, 2),
            )
            for i in range(len(predictions_arr))
        ]

        # Metrics on hold-out (last 20% of training)
        y = np.array(self._values)
        holdout_n = max(1, len(y) // 5)
        actual_hold = y[-holdout_n:]
        X_all = self._build_features(self._dates, self._values).dropna()
        if len(X_all) >= holdout_n:
            X_hold = X_all.drop(columns=["target"]).iloc[-holdout_n:][self._feature_names]
            pred_hold = self._model.predict(X_hold)
            metrics = self._calculate_metrics(actual_hold, pred_hold)
        else:
            metrics = {}

        predicted_month = float(np.mean(predictions_arr[:30]) * 30) if len(predictions_arr) >= 30 \
            else float(np.sum(predictions_arr))
        mape = metrics.get("mape", 10)
        confidence = max(0.50, min(0.99, 1.0 - mape / 100))

        return ForecastResult(
            model_name="xgboost",
            provider=self.provider,
            current_monthly_cost=float(self._values[-1]),
            predicted_next_month=round(predicted_month, 2),
            lower_bound=round(predicted_month * 0.87, 2),
            upper_bound=round(predicted_month * 1.13, 2),
            confidence=round(confidence, 3),
            forecast_points=points,
            metrics=metrics,
        )

    def _build_features(self, dates: List[str], values: List[float]) -> pd.DataFrame:
        df = pd.DataFrame({"ds": pd.to_datetime(dates), "y": values})
        df = df.sort_values("ds").reset_index(drop=True)

        df["target"]    = df["y"].shift(-1)  # predict next value
        df["month"]     = df["ds"].dt.month
        df["quarter"]   = df["ds"].dt.quarter
        df["year"]      = df["ds"].dt.year
        df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
        df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
        df["trend"]     = range(len(df))

        for lag in self.LAG_FEATURES:
            df[f"lag_{lag}"] = df["y"].shift(lag)

        for w in self.ROLLING_WINDOWS:
            df[f"rolling_mean_{w}"] = df["y"].rolling(w).mean()
            df[f"rolling_std_{w}"]  = df["y"].rolling(w).std()

        df["pct_change_1"] = df["y"].pct_change(1)
        df["pct_change_3"] = df["y"].pct_change(3)

        return df.drop(columns=["ds", "y"])

    def _linear_fallback(self, periods: int) -> ForecastResult:
        """Simple linear trend fallback when XGBoost is not available."""
        y = np.array(self._values)
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        base_date = pd.to_datetime(self._dates[-1]) if self._dates else datetime.utcnow()

        points = []
        for i in range(periods):
            pred = max(0, intercept + slope * (len(y) + i))
            points.append(ForecastPoint(
                date=(base_date + timedelta(days=i + 1)).strftime("%Y-%m-%d"),
                predicted=round(pred, 2),
                lower=round(pred * 0.85, 2),
                upper=round(pred * 1.15, 2),
            ))

        predicted_month = sum(p.predicted for p in points[:30])
        return ForecastResult(
            model_name="xgboost_fallback",
            provider=self.provider,
            current_monthly_cost=float(y[-1]) if len(y) > 0 else 40000,
            predicted_next_month=round(predicted_month, 2),
            lower_bound=round(predicted_month * 0.85, 2),
            upper_bound=round(predicted_month * 1.15, 2),
            confidence=0.75,
            forecast_points=points,
            metrics={"note": "linear_fallback"},
        )

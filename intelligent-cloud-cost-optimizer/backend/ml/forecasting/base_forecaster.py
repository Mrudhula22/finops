"""
Abstract base class for all cost forecasters.
All forecasters must produce a ForecastResult with the same shape.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np


@dataclass
class ForecastPoint:
    date: str
    predicted: float
    lower: float
    upper: float


@dataclass
class ForecastResult:
    model_name: str
    provider: str
    current_monthly_cost: float
    predicted_next_month: float
    lower_bound: float
    upper_bound: float
    confidence: float                    # 0-1
    forecast_points: List[ForecastPoint]
    metrics: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def budget_overrun(self) -> float:
        from config.settings import settings
        return max(0.0, self.predicted_next_month - settings.DEFAULT_MONTHLY_BUDGET)

    @property
    def overrun_risk(self) -> str:
        ratio = self.predicted_next_month / max(1, self._budget())
        if ratio < 0.75:  return "none"
        if ratio < 0.85:  return "low"
        if ratio < 1.0:   return "medium"
        return "high"

    def _budget(self) -> float:
        from config.settings import settings
        return settings.DEFAULT_MONTHLY_BUDGET


class BaseForecaster(ABC):

    @abstractmethod
    def fit(self, dates: List[str], values: List[float]) -> None:
        """Train the model on historical cost data."""
        ...

    @abstractmethod
    def predict(self, periods: int = 30) -> ForecastResult:
        """Generate forecast for the next N days."""
        ...

    @staticmethod
    def _generate_mock_history(months: int = 12, base: float = 35000.0) -> tuple:
        """Generate realistic cost history for testing."""
        import pandas as pd
        import numpy as np
        dates, values = [], []
        start = pd.Timestamp.now() - pd.DateOffset(months=months)
        for i in range(months):
            d = start + pd.DateOffset(months=i)
            # Simulate gradual growth + seasonality + noise
            trend = base + i * 800
            seasonal = 2000 * np.sin(2 * np.pi * i / 12)
            noise = np.random.normal(0, 500)
            values.append(max(0, trend + seasonal + noise))
            dates.append(d.strftime("%Y-%m-%d"))
        return dates, values

    @staticmethod
    def _calculate_metrics(actual: np.ndarray, predicted: np.ndarray) -> Dict[str, float]:
        if len(actual) == 0 or len(predicted) == 0:
            return {}
        mae  = float(np.mean(np.abs(actual - predicted)))
        mape = float(np.mean(np.abs((actual - predicted) / np.maximum(actual, 1))) * 100)
        rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))
        # R²
        ss_res = np.sum((actual - predicted) ** 2)
        ss_tot = np.sum((actual - np.mean(actual)) ** 2)
        r2 = float(1 - ss_res / max(ss_tot, 1e-9))
        return {"mae": round(mae, 2), "mape": round(mape, 2),
                "rmse": round(rmse, 2), "r2": round(r2, 4)}

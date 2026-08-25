"""
Experiment runner for comparing forecasting models.
Used for research paper results — compares ARIMA, Prophet, XGBoost, Ensemble.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from ml.forecasting.arima_model import ARIMAForecaster
from ml.forecasting.prophet_model import ProphetForecaster
from ml.forecasting.xgboost_model import XGBoostForecaster
from ml.forecasting.ensemble import EnsembleForecaster
from ml.evaluation.metrics import ModelEvaluator

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """Runs comparative experiments across all forecasting models."""

    def __init__(self):
        self.evaluator = ModelEvaluator(n_splits=5, test_size=1)

    def run_all(
        self,
        dates: List[str],
        values: List[float],
        provider: str = "all",
    ) -> Dict[str, Any]:
        """
        Compare all models on the same dataset.
        Returns a structured results dict suitable for the research paper.
        """
        forecasters = {
            "ARIMA":    ARIMAForecaster(provider),
            "Prophet":  ProphetForecaster(provider),
            "XGBoost":  XGBoostForecaster(provider),
            "Ensemble": EnsembleForecaster(provider),
        }

        logger.info("Running experiment comparison on %d data points for provider=%s",
                    len(values), provider)

        comparison = self.evaluator.compare_models(forecasters, dates, values)

        # Also generate sample forecasts from each model for visualisation
        sample_forecasts = {}
        for name, fc in forecasters.items():
            try:
                fc.fit(dates, values)
                result = fc.predict(periods=30)
                sample_forecasts[name] = {
                    "predicted_next_month": result.predicted_next_month,
                    "confidence": result.confidence,
                    "metrics": result.metrics,
                }
            except Exception as exc:
                logger.warning("Sample forecast for %s failed: %s", name, exc)

        return {
            "experiment_id": f"exp_{provider}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "provider": provider,
            "n_data_points": len(values),
            "date_range": {"start": dates[0] if dates else "", "end": dates[-1] if dates else ""},
            "cv_comparison": comparison,
            "sample_forecasts": sample_forecasts,
            "summary": self._build_summary(comparison, sample_forecasts),
        }

    def _build_summary(self, comparison: Dict, forecasts: Dict) -> Dict[str, Any]:
        ranking = comparison.get("ranking", [])
        best    = comparison.get("best_model", "Ensemble")

        rows = []
        for entry in ranking:
            model = entry["model"]
            mape  = entry["mape"]
            fc    = forecasts.get(model, {})
            rows.append({
                "rank": entry["rank"],
                "model": model,
                "mape_pct": mape,
                "predicted_next_month": fc.get("predicted_next_month", 0),
                "confidence_pct": round(fc.get("confidence", 0) * 100, 1),
            })

        return {
            "best_model": best,
            "table": rows,
            "recommendation": f"{best} achieved the lowest MAPE and is recommended for production forecasting.",
        }

    def save_results(self, results: Dict[str, Any], path: str) -> None:
        with open(path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info("Experiment results saved to %s", path)

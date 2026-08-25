"""
Model evaluation metrics for forecasting models.
Supports walk-forward cross-validation for time series.
"""

import logging
from typing import Any, Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class ModelEvaluator:
    """Evaluate forecasting models using time-series cross-validation."""

    def __init__(self, n_splits: int = 5, test_size: int = 1):
        self.n_splits  = n_splits
        self.test_size = test_size

    def walk_forward_cv(
        self,
        forecaster,
        dates: List[str],
        values: List[float],
        periods: int = 1,
    ) -> Dict[str, Any]:
        """
        Walk-forward cross-validation.
        Each fold trains on all data up to split point, tests on next `test_size` points.
        """
        n = len(values)
        min_train = max(6, n // (self.n_splits + 1))

        all_actual, all_predicted = [], []
        fold_results = []

        for fold in range(self.n_splits):
            train_end = min_train + fold * self.test_size
            if train_end + self.test_size > n:
                break

            train_dates  = dates[:train_end]
            train_values = values[:train_end]
            test_values  = values[train_end: train_end + self.test_size]

            try:
                forecaster.fit(train_dates, train_values)
                result = forecaster.predict(periods=self.test_size)

                if result.forecast_points:
                    preds = [pt.predicted for pt in result.forecast_points[:self.test_size]]
                else:
                    preds = [result.predicted_next_month] * self.test_size

                all_actual.extend(test_values)
                all_predicted.extend(preds[:len(test_values)])

                fold_metrics = self._metrics(
                    np.array(test_values),
                    np.array(preds[:len(test_values)])
                )
                fold_results.append({"fold": fold + 1, **fold_metrics})
                logger.debug("CV fold %d: %s", fold + 1, fold_metrics)

            except Exception as exc:
                logger.warning("CV fold %d error: %s", fold + 1, exc)

        if not all_actual:
            return {"error": "insufficient_data"}

        overall = self._metrics(np.array(all_actual), np.array(all_predicted))
        return {
            "model": getattr(forecaster, "__class__", type(forecaster)).__name__,
            "n_folds": len(fold_results),
            "overall": overall,
            "folds": fold_results,
        }

    def compare_models(
        self,
        forecasters: Dict[str, Any],
        dates: List[str],
        values: List[float],
    ) -> Dict[str, Any]:
        """Compare multiple forecasters on the same dataset."""
        results = {}
        for name, fc in forecasters.items():
            logger.info("Evaluating model: %s", name)
            results[name] = self.walk_forward_cv(fc, dates, values)

        # Rank by MAPE (ascending)
        ranked = sorted(
            [(name, r.get("overall", {}).get("mape", 999)) for name, r in results.items()],
            key=lambda x: x[1],
        )
        return {
            "results": results,
            "ranking": [{"rank": i + 1, "model": name, "mape": round(mape, 2)}
                        for i, (name, mape) in enumerate(ranked)],
            "best_model": ranked[0][0] if ranked else None,
        }

    @staticmethod
    def _metrics(actual: np.ndarray, predicted: np.ndarray) -> Dict[str, float]:
        if len(actual) == 0:
            return {}
        mae   = float(np.mean(np.abs(actual - predicted)))
        mape  = float(np.mean(np.abs((actual - predicted) / np.maximum(actual, 1))) * 100)
        rmse  = float(np.sqrt(np.mean((actual - predicted) ** 2)))
        ss_res = float(np.sum((actual - predicted) ** 2))
        ss_tot = float(np.sum((actual - np.mean(actual)) ** 2))
        r2    = 1.0 - ss_res / max(ss_tot, 1e-9)
        return {
            "mae":  round(mae, 2),
            "mape": round(mape, 2),
            "rmse": round(rmse, 2),
            "r2":   round(r2, 4),
        }

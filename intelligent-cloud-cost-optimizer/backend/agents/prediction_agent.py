"""
Prediction Agent.
Runs cost forecasting models and detects anomalies.
Reads historical data from agent memory set by DataAgent.
"""

import logging
from typing import Any, Dict, List

from agents.base_agent import BaseAgent, AgentMemory, AgentResult
from config.settings import settings
from ml.forecasting.ensemble import EnsembleForecaster
from ml.forecasting.arima_model import ARIMAForecaster
from ml.forecasting.prophet_model import ProphetForecaster
from ml.forecasting.xgboost_model import XGBoostForecaster
from ml.anomaly_detection.isolation_forest import IsolationForestDetector
from ml.anomaly_detection.threshold_detection import ThresholdDetector

logger = logging.getLogger(__name__)

MODEL_MAP = {
    "arima":    ARIMAForecaster,
    "prophet":  ProphetForecaster,
    "xgboost":  XGBoostForecaster,
    "ensemble": EnsembleForecaster,
}


class PredictionAgent(BaseAgent):
    """Forecasts future cloud costs and flags anomalies."""

    def __init__(self, memory: AgentMemory = None):
        super().__init__("prediction_agent", memory)

    async def _execute(self, context: Dict[str, Any]) -> AgentResult:
        model_name = context.get("model", "ensemble")
        periods    = context.get("periods", 30)
        action     = context.get("action", "forecast_costs")

        historical   = self.memory.get("historical")
        monthly_summ = self.memory.get("monthly_summary", {})

        if not historical:
            self._add_message("system", "No historical data in memory — running data collection first.")
            from agents.data_agent import DataAgent
            da = DataAgent(self.memory)
            await da.run({"action": "collect_all_costs"})
            historical   = self.memory.get("historical", {})
            monthly_summ = self.memory.get("monthly_summary", {})

        # ── Forecast per provider ─────────────────────────────────────────────
        forecasts: Dict[str, Any] = {}
        for provider in ["aws", "azure", "gcp"]:
            history_data = historical.get(provider, [])
            if not history_data:
                continue
            dates  = [h["date"] for h in history_data]
            values = [h["cost"] for h in history_data]

            ForecasterClass = MODEL_MAP.get(model_name, EnsembleForecaster)
            fc = ForecasterClass(provider=provider)
            fc.fit(dates, values)
            result = fc.predict(periods=periods)
            forecasts[provider] = {
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

        # ── Combined total forecast ───────────────────────────────────────────
        total_predicted = sum(
            f.get("predicted_next_month", 0) for f in forecasts.values()
        )
        budget = settings.DEFAULT_MONTHLY_BUDGET
        total_overrun = max(0, total_predicted - budget)
        overall_risk  = "high" if total_predicted > budget else \
                        "medium" if total_predicted > budget * 0.85 else "low"

        # ── Anomaly detection ─────────────────────────────────────────────────
        anomalies = self._detect_anomalies(historical, monthly_summ, budget)

        prediction_output = {
            "forecasts":      forecasts,
            "total_predicted": round(total_predicted, 2),
            "monthly_budget":  budget,
            "total_overrun":   round(total_overrun, 2),
            "overall_risk":    overall_risk,
            "anomalies":       anomalies,
            "model_used":      model_name,
        }

        self.memory.set("predictions", prediction_output)

        reasoning = (
            f"Predicted total next month: ₹{total_predicted:,.0f} | "
            f"Budget: ₹{budget:,.0f} | "
            f"{'OVERRUN: ₹' + f'{total_overrun:,.0f}' if total_overrun > 0 else 'Within budget'} | "
            f"Risk: {overall_risk.upper()} | Anomalies: {len(anomalies)}"
        )
        self._add_message("assistant", reasoning)

        return AgentResult(
            agent_name=self.name,
            success=True,
            data=prediction_output,
            reasoning=reasoning,
        )

    def _detect_anomalies(
        self,
        historical: Dict[str, List],
        monthly_summ: Dict[str, float],
        budget: float,
    ) -> List[Dict[str, Any]]:
        anomalies = []
        threshold = ThresholdDetector()

        for provider in ["aws", "azure", "gcp"]:
            hist = historical.get(provider, [])
            if len(hist) < 3:
                continue
            values = [h["cost"] for h in hist]
            current = values[-1]
            previous = values[-2]

            # Budget check
            budget_anomaly = threshold.detect_budget_breach(current, budget / 3, provider)
            if budget_anomaly:
                anomalies.append(budget_anomaly.__dict__)

            # Spike check
            spike_anomaly = threshold.detect_cost_spike(provider, provider, previous, current)
            if spike_anomaly:
                anomalies.append(spike_anomaly.__dict__)

            # Statistical anomaly via IsolationForest
            if len(values) >= 6:
                detector = IsolationForestDetector(contamination=0.1)
                dates = [h["date"] for h in hist]
                statistical = detector.detect(provider, provider, dates, values, "monthly_cost")
                anomalies.extend([a.__dict__ for a in statistical[-2:]])  # top 2

        return anomalies

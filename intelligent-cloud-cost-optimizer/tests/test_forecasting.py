"""Tests for ML forecasting models."""
import pytest
from ml.forecasting.base_forecaster import BaseForecaster
from ml.forecasting.arima_model import ARIMAForecaster
from ml.forecasting.prophet_model import ProphetForecaster
from ml.forecasting.xgboost_model import XGBoostForecaster
from ml.forecasting.ensemble import EnsembleForecaster

def _mock_data():
    base = BaseForecaster
    dates, values = base._generate_mock_history(12, 35000)
    return dates, values

def test_arima_predict():
    dates, values = _mock_data()
    fc = ARIMAForecaster("aws")
    fc.fit(dates, values)
    result = fc.predict(30)
    assert result.predicted_next_month > 0
    assert len(result.forecast_points) == 30
    assert 0 < result.confidence <= 1

def test_prophet_predict():
    dates, values = _mock_data()
    fc = ProphetForecaster("azure")
    fc.fit(dates, values)
    result = fc.predict(30)
    assert result.predicted_next_month > 0

def test_xgboost_predict():
    dates, values = _mock_data()
    fc = XGBoostForecaster("gcp")
    fc.fit(dates, values)
    result = fc.predict(30)
    assert result.predicted_next_month > 0

def test_ensemble_predict():
    dates, values = _mock_data()
    fc = EnsembleForecaster("aws")
    fc.fit(dates, values)
    result = fc.predict(30)
    assert result.model_name == "ensemble"
    assert result.predicted_next_month > 0
    assert len(result.forecast_points) > 0

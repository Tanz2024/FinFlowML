from datetime import date
from decimal import Decimal

from backend.app.services.forecasting import NaiveAverageForecastingProvider, RevenuePoint


def test_naive_average_forecast_extends_history():
    history = [
        RevenuePoint(period=date(2026, 1, 1), revenue=Decimal("100")),
        RevenuePoint(period=date(2026, 2, 1), revenue=Decimal("200")),
    ]
    forecasts = NaiveAverageForecastingProvider().forecast(history, periods_ahead=2)
    assert [f.period for f in forecasts] == [date(2026, 3, 1), date(2026, 4, 1)]
    assert all(f.predicted_revenue == Decimal("150") for f in forecasts)


def test_naive_average_forecast_handles_empty_history():
    assert NaiveAverageForecastingProvider().forecast([], periods_ahead=3) == []

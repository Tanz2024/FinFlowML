"""Forecasting service interface.

Defines the provider contract that future forecasting backends (Prophet, XGBoost,
transformer-based models) will implement. Only a deterministic baseline provider is
implemented today; it exists to validate the interface, not to be a serious forecast.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class RevenuePoint:
    period: date
    revenue: Decimal


@dataclass
class ForecastPoint:
    period: date
    predicted_revenue: Decimal


class ForecastingProvider(ABC):
    """Contract for a revenue forecasting backend."""

    @abstractmethod
    def forecast(self, history: list[RevenuePoint], periods_ahead: int) -> list[ForecastPoint]:
        """Given historical revenue points (chronological), predict future periods."""
        raise NotImplementedError


class NaiveAverageForecastingProvider(ForecastingProvider):
    """Baseline provider: repeats the trailing average. Placeholder for real models."""

    def forecast(self, history: list[RevenuePoint], periods_ahead: int) -> list[ForecastPoint]:
        if not history or periods_ahead <= 0:
            return []
        average = sum((point.revenue for point in history), start=Decimal("0")) / len(history)
        last_period = history[-1].period
        forecasts = []
        for offset in range(1, periods_ahead + 1):
            month = last_period.month + offset
            year = last_period.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            forecasts.append(ForecastPoint(period=date(year, month, 1), predicted_revenue=average))
        return forecasts

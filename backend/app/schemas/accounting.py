from decimal import Decimal

from pydantic import BaseModel, Field


class AccountingSummaryRead(BaseModel):
    total_revenue: Decimal
    total_expenses: Decimal
    net_profit: Decimal
    by_currency: dict[str, dict[str, Decimal]] = Field(default_factory=dict)


class MonthlyReportEntryRead(BaseModel):
    month: str
    revenue: Decimal
    expenses: Decimal
    profit: Decimal
    currency: str | None = None

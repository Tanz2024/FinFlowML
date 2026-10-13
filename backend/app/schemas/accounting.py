from decimal import Decimal

from pydantic import BaseModel


class AccountingSummaryRead(BaseModel):
    total_revenue: Decimal
    total_expenses: Decimal
    net_profit: Decimal


class MonthlyReportEntryRead(BaseModel):
    month: str
    revenue: Decimal
    expenses: Decimal
    profit: Decimal

"""Accounting foundation: revenue, expense, and profit aggregation.

Revenue is recognized from paid invoice totals (via Payment records); expenses come
from the Expense ledger built by the receipt pipeline. This module is read-only
aggregation over existing tables — it does not own any new persisted state.
"""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.expense import Expense
from backend.app.models.payment import Payment


@dataclass
class AccountingSummary:
    total_revenue: Decimal
    total_expenses: Decimal
    net_profit: Decimal


@dataclass
class MonthlyReportEntry:
    month: str
    revenue: Decimal
    expenses: Decimal
    profit: Decimal


def get_summary(db: Session, organization_id=None) -> AccountingSummary:
    revenue = sum((p.amount_paid for p in db.scalars(select(Payment).where(Payment.organization_id == organization_id)).all()), start=Decimal("0"))
    expenses = sum((e.amount for e in db.scalars(select(Expense).where(Expense.organization_id == organization_id)).all()), start=Decimal("0"))
    return AccountingSummary(
        total_revenue=revenue, total_expenses=expenses, net_profit=revenue - expenses
    )


def get_monthly_report(db: Session, organization_id=None) -> list[MonthlyReportEntry]:
    revenue_by_month: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    expenses_by_month: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for payment in db.scalars(select(Payment).where(Payment.organization_id == organization_id)).all():
        month = payment.payment_date.strftime("%Y-%m")
        revenue_by_month[month] += payment.amount_paid

    for expense in db.scalars(select(Expense).where(Expense.organization_id == organization_id)).all():
        month = expense.expense_date.strftime("%Y-%m") if expense.expense_date else "unknown"
        expenses_by_month[month] += expense.amount

    months = sorted(set(revenue_by_month) | set(expenses_by_month))
    return [
        MonthlyReportEntry(
            month=month,
            revenue=revenue_by_month[month],
            expenses=expenses_by_month[month],
            profit=revenue_by_month[month] - expenses_by_month[month],
        )
        for month in months
    ]

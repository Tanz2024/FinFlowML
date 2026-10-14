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
from backend.app.models.invoice import Invoice
from backend.app.models.payment import Payment


@dataclass
class AccountingSummary:
    total_revenue: Decimal
    total_expenses: Decimal
    net_profit: Decimal
    by_currency: dict[str, dict[str, Decimal]]


@dataclass
class MonthlyReportEntry:
    month: str
    revenue: Decimal
    expenses: Decimal
    profit: Decimal
    currency: str | None = None


def get_summary(db: Session, organization_id=None) -> AccountingSummary:
    revenue_by_currency: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    expense_by_currency: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for payment, invoice in db.execute(select(Payment, Invoice).join(Invoice, Payment.invoice_id == Invoice.id).where(Payment.organization_id == organization_id, Invoice.organization_id == organization_id)).all(): revenue_by_currency[invoice.currency] += payment.amount_paid
    for expense in db.scalars(select(Expense).where(Expense.organization_id == organization_id)).all(): expense_by_currency[expense.currency] += expense.amount
    currencies = set(revenue_by_currency) | set(expense_by_currency)
    revenue = sum(revenue_by_currency.values(), start=Decimal("0")) if len(currencies) <= 1 else Decimal("0")
    expenses = sum(expense_by_currency.values(), start=Decimal("0")) if len(currencies) <= 1 else Decimal("0")
    return AccountingSummary(
        total_revenue=revenue, total_expenses=expenses, net_profit=revenue - expenses,
        by_currency={currency: {"revenue": revenue_by_currency[currency], "expenses": expense_by_currency[currency], "profit": revenue_by_currency[currency] - expense_by_currency[currency]} for currency in sorted(currencies)},
    )


def get_monthly_report(db: Session, organization_id=None) -> list[MonthlyReportEntry]:
    revenue_by_month: defaultdict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    expenses_by_month: defaultdict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))

    for payment, invoice in db.execute(select(Payment, Invoice).join(Invoice, Payment.invoice_id == Invoice.id).where(Payment.organization_id == organization_id, Invoice.organization_id == organization_id)).all():
        revenue_by_month[(payment.payment_date.strftime("%Y-%m"), invoice.currency)] += payment.amount_paid

    for expense in db.scalars(select(Expense).where(Expense.organization_id == organization_id)).all():
        month = expense.expense_date.strftime("%Y-%m") if expense.expense_date else "unknown"
        expenses_by_month[(month, expense.currency)] += expense.amount

    months = sorted(set(revenue_by_month) | set(expenses_by_month))
    return [
        MonthlyReportEntry(
            month=month,
            revenue=revenue_by_month[(month, currency)],
            expenses=expenses_by_month[(month, currency)],
            profit=revenue_by_month[(month, currency)] - expenses_by_month[(month, currency)],
            currency=currency,
        )
        for month, currency in months
    ]

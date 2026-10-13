"""Automated receipt-to-expense pipeline.

Image -> OCR -> FinFlowML extraction -> Receipt storage -> Expense creation -> Category
assignment. This module owns the last two steps: given a persisted Receipt, it derives
a normalized Expense with merchant/category matching and currency normalization.
"""

from sqlalchemy.orm import Session

from backend.app.models.expense import Expense
from backend.app.models.receipt import Receipt
from backend.app.services.category_matcher import categorize_merchant
from backend.app.services.currency import normalize_amount, normalize_currency


def create_expense_from_receipt(db: Session, receipt: Receipt) -> Expense:
    """Derive and persist an Expense from a Receipt's structured extraction data.

    Idempotent-ish: callers should only invoke this once per receipt; the caller is
    responsible for deciding whether a receipt has already been converted.
    """
    category = categorize_merchant(db, receipt.company)
    expense = Expense(
        receipt_id=receipt.id,
        category_id=category.id,
        merchant_name=receipt.company,
        expense_date=receipt.receipt_date,
        amount=normalize_amount(receipt.total),
        currency=normalize_currency(receipt.currency),
    )
    db.add(expense)
    db.flush()
    return expense


def process_receipt(db: Session, receipt: Receipt) -> Expense:
    """Run the full post-storage pipeline for a receipt and commit the result."""
    expense = create_expense_from_receipt(db, receipt)
    receipt.status = "processed"
    db.commit()
    db.refresh(expense)
    return expense

"""Keyword-based merchant-to-category matching for automated expense creation."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.expense_category import ExpenseCategory

UNCATEGORIZED = "Uncategorized"

# Ordered merchant keyword -> category name. First match wins.
MERCHANT_CATEGORY_RULES: list[tuple[str, str]] = [
    ("restaurant", "Food & Dining"),
    ("cafe", "Food & Dining"),
    ("coffee", "Food & Dining"),
    ("grocery", "Groceries"),
    ("market", "Groceries"),
    ("pharmacy", "Health"),
    ("clinic", "Health"),
    ("hospital", "Health"),
    ("gas", "Transportation"),
    ("fuel", "Transportation"),
    ("uber", "Transportation"),
    ("taxi", "Transportation"),
    ("airlines", "Travel"),
    ("hotel", "Travel"),
    ("office", "Office Supplies"),
    ("supplies", "Office Supplies"),
    ("electric", "Utilities"),
    ("utility", "Utilities"),
]


def match_category_name(merchant_name: str | None) -> str:
    """Return the best-guess category name for a merchant, or Uncategorized."""
    if not merchant_name:
        return UNCATEGORIZED
    lowered = merchant_name.lower()
    for keyword, category_name in MERCHANT_CATEGORY_RULES:
        if keyword in lowered:
            return category_name
    return UNCATEGORIZED


def get_or_create_category(db: Session, name: str, organization_id=None) -> ExpenseCategory:
    """Fetch a category by name, creating it (as a system category) if absent."""
    category = db.scalar(select(ExpenseCategory).where(ExpenseCategory.name == name, ExpenseCategory.organization_id == organization_id))
    if category is not None:
        return category
    category = ExpenseCategory(name=name, organization_id=organization_id, is_system=True)
    db.add(category)
    db.flush()
    return category


def categorize_merchant(db: Session, merchant_name: str | None, organization_id=None) -> ExpenseCategory:
    """Resolve (and persist if needed) the expense category for a merchant."""
    return get_or_create_category(db, match_category_name(merchant_name), organization_id)

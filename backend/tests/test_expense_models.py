from decimal import Decimal

from backend.app.models.expense import Expense
from backend.app.models.expense_category import ExpenseCategory
from backend.app.models.receipt import Receipt


def test_phase2_models_expose_receipt_expense_relationships():
    receipt = Receipt(company="Market", total=Decimal("12.50"))
    category = ExpenseCategory(name="Food", is_system=True)
    expense = Expense(amount=Decimal("12.50"), currency="USD", receipt=receipt, category=category)

    assert expense.receipt.company == "Market"
    assert expense.category.name == "Food"

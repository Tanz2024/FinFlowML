from decimal import Decimal
from uuid import UUID

from backend.app.models.receipt import Receipt
from backend.app.services.category_matcher import match_category_name
from backend.app.services.currency import normalize_amount, normalize_currency
from backend.app.services.expense_pipeline import process_receipt


def test_match_category_name_known_merchant():
    assert match_category_name("Downtown Cafe") == "Food & Dining"
    assert match_category_name("Random Widgets Co") == "Uncategorized"
    assert match_category_name(None) == "Uncategorized"


def test_normalize_currency_and_amount():
    assert normalize_currency("$") == "USD"
    assert normalize_currency(None) == "USD"
    assert normalize_currency("eur") == "EUR"
    assert normalize_amount("12.345") == Decimal("12.35")
    assert normalize_amount(None) == Decimal("0.00")


def test_receipt_creation_waits_for_review_and_does_not_create_expense(client, client_db):
    response = client.post(
        "/receipts",
        json={
            "extracted_data": {"company": "Blue Cafe", "total": "9.99"},
            "company": "Blue Cafe",
            "total": "9.99",
            "currency": "usd",
        },
    )
    assert response.status_code == 201
    receipt = client_db.get(Receipt, UUID(response.json()["id"]))
    assert receipt.status == "needs_review"
    assert len(receipt.expenses) == 0


def test_process_receipt_falls_back_to_uncategorized(client_db):
    receipt = Receipt(company="Widgets Inc", total=Decimal("5.00"), currency="USD")
    client_db.add(receipt)
    client_db.commit()
    client_db.refresh(receipt)

    expense = process_receipt(client_db, receipt)
    assert expense.category.name == "Uncategorized"

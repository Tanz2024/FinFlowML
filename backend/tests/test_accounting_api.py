from datetime import date
from decimal import Decimal

from backend.app.models.expense import Expense
from backend.app.models.expense_category import ExpenseCategory
from backend.app.models.receipt import Receipt


def _create_customer(client):
    return client.post("/customers", json={"name": "Acme Corp"}).json()


def test_invoice_creation_with_items_and_customer_check(client):
    missing_customer = client.post(
        "/invoices",
        json={
            "customer_id": "00000000-0000-0000-0000-000000000000",
            "invoice_number": "INV-1",
            "invoice_date": "2026-01-01",
            "due_date": "2026-01-15",
            "subtotal": "100.00",
            "tax": "10.00",
            "total": "110.00",
            "currency": "USD",
            "status": "unpaid",
        },
    )
    assert missing_customer.status_code == 404

    customer = _create_customer(client)
    response = client.post(
        "/invoices",
        json={
            "customer_id": customer["id"],
            "invoice_number": "INV-2",
            "invoice_date": "2026-01-01",
            "due_date": "2026-01-15",
            "subtotal": "100.00",
            "tax": "10.00",
            "total": "110.00",
            "currency": "USD",
            "status": "unpaid",
            "items": [
                {"description": "Consulting", "quantity": "2", "unit_price": "50.00", "amount": "100.00"}
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["description"] == "Consulting"


def test_accounting_summary_and_monthly_report(client, client_db):
    customer = _create_customer(client)
    invoice = client.post(
        "/invoices",
        json={
            "customer_id": customer["id"],
            "invoice_number": "INV-3",
            "invoice_date": "2026-02-01",
            "due_date": "2026-02-15",
            "subtotal": "200.00",
            "tax": "0.00",
            "total": "200.00",
            "currency": "USD",
            "status": "unpaid",
        },
    ).json()
    client.post(
        "/payments",
        json={"invoice_id": invoice["id"], "payment_date": "2026-02-05", "amount_paid": "200.00"},
    )

    category = ExpenseCategory(name="Ops", is_system=True)
    client_db.add(category)
    client_db.commit()
    client_db.refresh(category)
    receipt = Receipt(company="Ops Supplies", total=Decimal("50.00"), currency="USD")
    client_db.add(receipt)
    client_db.commit()
    client_db.refresh(receipt)
    client_db.add(
        Expense(
            receipt_id=receipt.id,
            category_id=category.id,
            amount=Decimal("50.00"),
            currency="USD",
            expense_date=date.fromisoformat(invoice["invoice_date"]),
        )
    )
    client_db.commit()

    summary = client.get("/accounting/summary").json()
    assert summary["total_revenue"] == "200.00"
    assert summary["total_expenses"] == "50.00"
    assert summary["net_profit"] == "150.00"

    report = client.get("/accounting/monthly-report").json()
    assert any(entry["month"] == "2026-02" for entry in report)


def test_assistant_context_endpoint(client, client_db):
    category = ExpenseCategory(name="Food & Dining", is_system=True)
    client_db.add(category)
    client_db.commit()
    client_db.refresh(category)
    receipt = Receipt(company="Cafe", total=Decimal("15.00"), currency="USD")
    client_db.add(receipt)
    client_db.commit()
    client_db.refresh(receipt)
    client_db.add(
        Expense(receipt_id=receipt.id, category_id=category.id, amount=Decimal("15.00"), currency="USD")
    )
    client_db.commit()

    response = client.get("/assistant/context", params={"q": "How much did I spend on Food & Dining?"})
    assert response.status_code == 200
    facts = {fact["label"]: fact["value"] for fact in response.json()["facts"]}
    assert facts["spending_on_Food & Dining"] == "15.00"

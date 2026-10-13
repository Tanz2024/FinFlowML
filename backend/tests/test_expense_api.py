from uuid import uuid4

from backend.app.models.expense_category import ExpenseCategory


def test_receipt_and_expense_apis_and_summary(client, client_db):
    category = ExpenseCategory(name="Supplies", is_system=True)
    client_db.add(category)
    client_db.commit()
    client_db.refresh(category)

    receipt = client.post(
        "/receipts",
        json={
            "extracted_data": {"company": "Shop", "total": "25.00"},
            "ocr_text": "TOTAL 25.00",
            "image_reference": "receipts/a.jpg",
            "company": "Shop",
            "total": "25.00",
            "currency": "USD",
        },
    )
    assert receipt.status_code == 201

    manual_receipt = client.post(
        "/receipts",
        json={
            "extracted_data": {},
            "currency": "USD",
        },
    )
    expense = client.post(
        "/expenses",
        json={
            "receipt_id": manual_receipt.json()["id"],
            "category_id": str(category.id),
            "amount": "25.00",
            "currency": "USD",
        },
    )
    assert expense.status_code == 409

    summary = client.get("/expenses/summary")
    assert summary.status_code == 200
    body = summary.json()
    # Unapproved receipt creation cannot enter the expense ledger.
    assert body["total_spending"] == "0"
    assert body["spending_by_category"] == {}
    assert "Uncategorized" not in body["spending_by_category"]

    categories = client.get("/expenses/categories")
    assert categories.json()[0]["name"] == "Supplies"


def test_expense_rejects_unknown_receipt(client):
    response = client.post(
        "/expenses",
        json={"receipt_id": str(uuid4()), "amount": "1.00", "currency": "USD"},
    )
    assert response.status_code == 404

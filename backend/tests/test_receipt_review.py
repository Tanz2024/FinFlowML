from uuid import UUID

from sqlalchemy import select

from backend.app.models.expense import Expense


def create_review_receipt(client):
    response = client.post(
        "/receipts",
        json={
            "extracted_data": {"company": "Cafe", "date": "2025-01-01", "address": "Road", "total": "10.00", "currency": "USD"},
            "company": "Cafe",
            "receipt_date": "2025-01-01",
            "address": "Road",
            "total": "10.00",
            "currency": "USD",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_review_correction_and_idempotent_approval(client, client_db):
    receipt = create_review_receipt(client)
    assert receipt["status"] == "needs_review"
    assert client.get("/receipts/pending").json()[0]["id"] == receipt["id"]
    correction = client.patch(
        f"/receipts/{receipt['id']}/corrections",
        json={"corrections": {"total": "12.50", "company": "Correct Cafe"}},
    )
    assert correction.status_code == 200
    assert correction.json()["raw_extracted_data"]["company"] == "Cafe"
    assert correction.json()["corrected_data"]["company"] == "Correct Cafe"
    first = client.post(f"/receipts/{receipt['id']}/approve")
    second = client.post(f"/receipts/{receipt['id']}/approve")
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert client_db.query(Expense).filter(Expense.receipt_id == UUID(receipt["id"])).count() == 1
    assert client.get(f"/receipts/{receipt['id']}/status").json()["status"] == "approved"


def test_invalid_values_block_approval(client):
    receipt = create_review_receipt(client)
    response = client.patch(
        f"/receipts/{receipt['id']}/corrections",
        json={"corrections": {"total": "0", "currency": "US", "receipt_date": "2099-01-01"}},
    )
    assert response.status_code == 200
    approval = client.post(f"/receipts/{receipt['id']}/approve")
    assert approval.status_code == 422


def test_rejection_is_terminal_and_does_not_create_expense(client, client_db):
    receipt = create_review_receipt(client)
    rejected = client.post(f"/receipts/{receipt['id']}/reject")
    assert rejected.status_code == 200
    assert client.post(f"/receipts/{receipt['id']}/approve").status_code == 409
    assert client_db.scalar(select(Expense).where(Expense.receipt_id == UUID(receipt["id"]))) is None

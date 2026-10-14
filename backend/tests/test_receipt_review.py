from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.models.expense import Expense
from backend.app.models.receipt import Receipt
from backend.app.services import receipt_review


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


def test_review_projection_exposes_each_value_and_field_errors(client):
    receipt = create_review_receipt(client)
    review = client.get(f"/receipts/{receipt['id']}/review")
    assert review.status_code == 200
    body = review.json()
    assert body["fields"]["receipt_date"]["original_model_value"] == "2025-01-01"
    assert body["fields"]["receipt_date"]["normalized_value"] == "2025-01-01"
    assert body["fields"]["receipt_date"]["effective_value"] == "2025-01-01"
    assert body["fields"]["receipt_date"]["status"] == "valid"

    correction = client.patch(
        f"/receipts/{receipt['id']}/corrections",
        json={"corrections": {"receipt_date": "not-a-date"}},
    )
    assert correction.status_code == 200
    corrected = client.get(f"/receipts/{receipt['id']}/review").json()
    field = corrected["fields"]["receipt_date"]
    assert field["reviewer_corrected_value"] == "not-a-date"
    assert field["effective_value"] == "not-a-date"
    assert field["status"] == "invalid"
    assert "receipt_date must be an ISO date" in field["errors"]
    assert client.post(f"/receipts/{receipt['id']}/approve").status_code == 422


def test_rejection_is_terminal_and_does_not_create_expense(client, client_db):
    receipt = create_review_receipt(client)
    rejected = client.post(f"/receipts/{receipt['id']}/reject")
    assert rejected.status_code == 200
    assert client.post(f"/receipts/{receipt['id']}/approve").status_code == 409
    assert client_db.scalar(select(Expense).where(Expense.receipt_id == UUID(receipt["id"]))) is None


def test_approval_transaction_failure_rolls_back(client, client_db, monkeypatch):
    receipt = create_review_receipt(client)
    item = client_db.get(Receipt, UUID(receipt["id"]))

    def fail(*args, **kwargs):
        raise SQLAlchemyError("simulated database failure")

    monkeypatch.setattr(receipt_review, "categorize_merchant", fail)
    with pytest.raises(SQLAlchemyError):
        receipt_review.approve_receipt(client_db, item)
    client_db.rollback()
    assert client_db.get(Receipt, item.id).status == "needs_review"
    assert client_db.scalar(select(Expense).where(Expense.receipt_id == item.id)) is None

from datetime import date
from decimal import Decimal
from uuid import uuid4

from backend.app.schemas.invoice import InvoiceCreate


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_customer_creation(client):
    response = client.post("/customers", json={"name": "Acme"})
    assert response.status_code == 201 and response.json()["name"] == "Acme"


def test_invoice_creation(client):
    customer = client.post("/customers", json={"name": "Acme"}).json()
    response = client.post(
        "/invoices",
        json={
            "customer_id": customer["id"],
            "invoice_number": "INV-1",
            "invoice_date": "2026-01-01",
            "due_date": "2026-01-31",
            "subtotal": "100.00",
            "tax": "6.00",
            "total": "106.00",
            "currency": "MYR",
            "status": "issued",
        },
    )
    assert response.status_code == 201 and response.json()["total"] == "106.00"


def test_payment_creation(client):
    customer = client.post("/customers", json={"name": "Acme"}).json()
    invoice = client.post(
        "/invoices",
        json={
            "customer_id": customer["id"],
            "invoice_number": "INV-2",
            "invoice_date": "2026-01-01",
            "due_date": "2026-01-31",
            "subtotal": "100.00",
            "tax": "0.00",
            "total": "100.00",
            "currency": "MYR",
            "status": "issued",
        },
    ).json()
    response = client.post(
        "/payments",
        json={"invoice_id": invoice["id"], "payment_date": "2026-01-15", "amount_paid": "50.00"},
    )
    assert response.status_code == 201 and response.json()["amount_paid"] == "50.00"


def test_schema_validation():
    value = InvoiceCreate(
        customer_id=uuid4(),
        invoice_number="INV",
        invoice_date=date.today(),
        due_date=date.today(),
        subtotal="1.20",
        tax="0.20",
        total="1.40",
        currency="USD",
        status="issued",
    )
    assert value.total == Decimal("1.40")

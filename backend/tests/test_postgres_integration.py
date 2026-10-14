"""Opt-in PostgreSQL concurrency coverage.

Run with FINFLOW_POSTGRES_TEST_URL=postgresql+psycopg://.../finflowml_test.
The database must already contain Alembic head; tests use unique rows and never
drop or truncate the database.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.models.customer import Customer
from backend.app.models.expense import Expense
from backend.app.models.extraction_job import ExtractionJob
from backend.app.models.invoice import Invoice
from backend.app.models.organization import Organization
from backend.app.models.payment import Payment
from backend.app.models.receipt import Receipt
from backend.app.services.extraction_jobs import claim_next
from backend.app.services.receipt_review import approve_receipt

URL = os.environ.get("FINFLOW_POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(not URL, reason="FINFLOW_POSTGRES_TEST_URL is not configured")


@pytest.fixture()
def pg_session_factory():
    engine = create_engine(URL, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def test_postgres_workers_claim_distinct_jobs(pg_session_factory):
    with pg_session_factory.begin() as db:
        org = Organization(name=f"pg-{uuid4()}")
        db.add(org)
        db.flush()
        for index in range(2):
            receipt = Receipt(organization_id=org.id, status="pending")
            db.add(receipt)
            db.flush()
            db.add(ExtractionJob(organization_id=org.id, receipt_id=receipt.id, idempotency_key=f"pg-{uuid4()}", payload_hash=str(index), storage_path="/tmp/test", state="queued"))

    def claim():
        with pg_session_factory() as db:
            job = claim_next(db)
            return job.id if job else None

    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(lambda _: claim(), range(2)))
    assert len(set(claimed)) == 2


def test_postgres_approval_is_exactly_once(pg_session_factory):
    with pg_session_factory.begin() as db:
        org = Organization(name=f"approval-{uuid4()}")
        db.add(org)
        db.flush()
        receipt = Receipt(organization_id=org.id, status="needs_review", company="Cafe", address="Road", receipt_date=date(2025, 1, 1), total=Decimal("2.00"), currency="USD", raw_extracted_data={"company": "Cafe", "address": "Road", "receipt_date": "2025-01-01", "total": "2.00", "currency": "USD"})
        db.add(receipt)
        db.flush()
        receipt_id, org_id = receipt.id, org.id

    def approve():
        with pg_session_factory() as db:
            item = db.get(Receipt, receipt_id)
            try:
                approve_receipt(db, item, organization_id=org_id)
            except Exception:
                db.rollback()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: approve(), range(2)))
    with pg_session_factory() as db:
        assert db.scalar(select(Receipt).where(Receipt.id == receipt_id)).status == "approved"
        assert len(db.scalars(select(Expense).where(Expense.receipt_id == receipt_id)).all()) == 1


def test_postgres_payments_lock_invoice_balance(pg_session_factory):
    """Two independent transactions may not commit payments beyond one invoice."""
    with pg_session_factory.begin() as db:
        org = Organization(name=f"payments-{uuid4()}")
        other = Organization(name=f"other-{uuid4()}")
        db.add_all([org, other])
        db.flush()
        customer = Customer(organization_id=org.id, name="Acceptance customer")
        db.add(customer)
        db.flush()
        invoice = Invoice(organization_id=org.id, customer_id=customer.id, invoice_number=f"pg-{uuid4()}", invoice_date=date(2025, 1, 1), due_date=date(2025, 2, 1), subtotal=Decimal("100.00"), tax=Decimal("0.00"), total=Decimal("100.00"), currency="USD")
        db.add(invoice)
        db.flush()
        invoice_id, org_id, other_id = invoice.id, org.id, other.id

    def pay(amount, organization_id):
        with pg_session_factory() as db:
            locked = db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id).with_for_update())
            if locked is None:
                db.rollback()
                return False
            paid = sum((item.amount_paid for item in locked.payments), start=Decimal("0.00"))
            if amount <= 0 or paid + amount > locked.total:
                db.rollback()
                return False
            db.add(Payment(organization_id=organization_id, invoice_id=locked.id, payment_date=date(2025, 1, 2), amount_paid=amount))
            db.commit()
            return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda value: pay(value, org_id), [Decimal("60.00"), Decimal("60.00")]))
    assert sorted(results) == [False, True]
    assert pay(Decimal("40.00"), org_id) is True
    assert pay(Decimal("1.00"), org_id) is False
    assert pay(Decimal("1.00"), other_id) is False
    with pg_session_factory() as db:
        assert db.scalar(select(Payment).where(Payment.invoice_id == invoice_id).with_for_update().execution_options(populate_existing=True)) is not None
        assert sum((item.amount_paid for item in db.scalars(select(Payment).where(Payment.invoice_id == invoice_id)).all()), start=Decimal("0.00")) == Decimal("100.00")

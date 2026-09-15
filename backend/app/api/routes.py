from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.models.customer import Customer
from backend.app.models.invoice import Invoice
from backend.app.models.payment import Payment
from backend.app.schemas.customer import CustomerCreate, CustomerRead
from backend.app.schemas.invoice import InvoiceCreate, InvoiceRead
from backend.app.schemas.payment import PaymentCreate, PaymentRead

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/customers", response_model=list[CustomerRead])
def list_customers(db: Session = Depends(get_db)):
    return db.scalars(select(Customer)).all()


@router.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    item = Customer(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/invoices", response_model=list[InvoiceRead])
def list_invoices(db: Session = Depends(get_db)):
    return db.scalars(select(Invoice)).all()


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: UUID, db: Session = Depends(get_db)):
    item = db.get(Invoice, invoice_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return item


@router.post("/invoices", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)):
    item = Invoice(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/payments", response_model=list[PaymentRead])
def list_payments(db: Session = Depends(get_db)):
    return db.scalars(select(Payment)).all()


@router.post("/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment(payload: PaymentCreate, db: Session = Depends(get_db)):
    item = Payment(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

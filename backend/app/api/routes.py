from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.auth import CurrentUser, create_access_token, require_permission
from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.models.customer import Customer
from backend.app.models.expense import Expense
from backend.app.models.expense_category import ExpenseCategory
from backend.app.models.extraction_job import ExtractionJob, ExtractionJobState
from backend.app.models.invoice import Invoice
from backend.app.models.organization import Membership, User
from backend.app.models.payment import Payment
from backend.app.models.receipt import Receipt
from backend.app.schemas.accounting import AccountingSummaryRead, MonthlyReportEntryRead
from backend.app.schemas.auth import LoginRequest, TokenResponse
from backend.app.schemas.customer import CustomerCreate, CustomerRead
from backend.app.schemas.expense import (
    ExpenseCategoryRead,
    ExpenseCreate,
    ExpenseRead,
    ExpenseSummary,
    ReceiptCorrection,
    ReceiptCreate,
    ReceiptRead,
    ReceiptStatusRead,
)
from backend.app.schemas.invoice import InvoiceCreate, InvoiceRead
from backend.app.schemas.payment import PaymentCreate, PaymentRead
from backend.app.services import accounting as accounting_service
from backend.app.services.financial_query import FinancialContext, build_context
from backend.app.services.invoicing import create_invoice as create_invoice_service
from backend.app.services.receipt_review import (
    approve_receipt,
    effective_data,
    reject_receipt,
    store_extraction,
    validate_receipt_data,
)

router = APIRouter()


@router.get("/jobs/{job_id}")
def extraction_job_status(job_id: UUID, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("read"))):
    job = db.scalar(select(ExtractionJob).where(ExtractionJob.id == job_id, ExtractionJob.organization_id == actor.organization_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Extraction job not found")
    return {"job_id": job.id, "receipt_id": job.receipt_id, "state": job.state, "retry_count": job.retry_count, "error_code": job.error_code, "error_message": job.error_message}


@router.post("/jobs/{job_id}/retry")
def retry_extraction_job(job_id: UUID, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("review"))):
    job = db.scalar(select(ExtractionJob).where(ExtractionJob.id == job_id, ExtractionJob.organization_id == actor.organization_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Extraction job not found")
    if job.state not in {ExtractionJobState.RETRYABLE_FAILED, ExtractionJobState.TERMINAL_FAILED}:
        raise HTTPException(status_code=409, detail="job is not failed")
    job.state = ExtractionJobState.QUEUED
    job.error_code = job.error_message = None
    job.next_attempt_at = None
    db.commit()
    return {"job_id": job.id, "state": job.state}


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    from backend.app.core.auth import verify_password
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    membership = next((m for m in memberships if m.organization_id == payload.organization_id), None) if payload.organization_id else (memberships[0] if len(memberships) == 1 else None)
    if not user.is_active or membership is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    return TokenResponse(
        access_token=create_access_token(user.id, membership.organization_id, membership.role),
        expires_in=settings.access_token_minutes * 60,
        organization_id=membership.organization_id,
        role=membership.role,
    )


def _owned(db: Session, model, record_id: UUID, actor: CurrentUser):
    item = db.scalar(select(model).where(model.id == record_id, model.organization_id == actor.organization_id))
    if item is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return item


@router.post("/receipts", response_model=ReceiptRead, status_code=status.HTTP_201_CREATED)
def create_receipt(payload: ReceiptCreate, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("review"))):
    item = Receipt(organization_id=actor.organization_id, **payload.model_dump())
    item.status = "pending"
    db.add(item)
    db.commit()
    db.refresh(item)
    return store_extraction(db, item)


@router.get("/receipts/pending", response_model=list[ReceiptRead])
def list_pending_receipts(db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("read"))):
    return db.scalars(select(Receipt).where(Receipt.organization_id == actor.organization_id, Receipt.status.in_(["pending", "needs_review"])).order_by(Receipt.created_at)).all()


@router.get("/receipts/{receipt_id}", response_model=ReceiptRead)
def get_receipt(receipt_id: UUID, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("read"))):
    item = _owned(db, Receipt, receipt_id, actor)
    return item


@router.get("/receipts/{receipt_id}/status", response_model=ReceiptStatusRead)
def receipt_status(receipt_id: UUID, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("read"))):
    item = _owned(db, Receipt, receipt_id, actor)
    expense = db.scalar(select(Expense).where(Expense.receipt_id == item.id, Expense.organization_id == actor.organization_id))
    return ReceiptStatusRead(id=item.id, status=item.status, validation_errors=item.validation_errors, effective_data=effective_data(item), expense_id=expense.id if expense else None)


@router.patch("/receipts/{receipt_id}/corrections", response_model=ReceiptRead)
def correct_receipt(receipt_id: UUID, payload: ReceiptCorrection, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("review"))):
    item = _owned(db, Receipt, receipt_id, actor)
    if item.status != "needs_review":
        raise HTTPException(status_code=409, detail="only receipts needing review can be corrected")
    unknown = set(payload.corrections) - {"company", "receipt_date", "address", "total", "currency"}
    if unknown:
        raise HTTPException(status_code=422, detail=f"unsupported correction fields: {sorted(unknown)}")
    item.corrected_data = {**(item.corrected_data or {}), **payload.corrections}
    item.corrected_by_user_id = actor.user.id
    item.last_action_by_user_id = actor.user.id
    item.validation_errors = validate_receipt_data(effective_data(item))
    db.commit()
    db.refresh(item)
    return item


@router.post("/receipts/{receipt_id}/approve", response_model=ExpenseRead)
def approve_receipt_endpoint(receipt_id: UUID, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("approve"))):
    return approve_receipt(db, _owned(db, Receipt, receipt_id, actor), actor.user.id, actor.organization_id)


@router.post("/receipts/{receipt_id}/reject", response_model=ReceiptRead)
def reject_receipt_endpoint(receipt_id: UUID, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("approve"))):
    return reject_receipt(db, _owned(db, Receipt, receipt_id, actor), actor.user.id)


@router.post("/expenses", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("manual_expense"))):
    receipt = _owned(db, Receipt, payload.receipt_id, actor)
    if receipt.status != "approved":
        raise HTTPException(status_code=409, detail="receipt must be approved before creating an expense")
    if payload.category_id is not None and db.scalar(select(ExpenseCategory).where(ExpenseCategory.id == payload.category_id, ExpenseCategory.organization_id == actor.organization_id)) is None:
        raise HTTPException(status_code=404, detail="Expense category not found")
    item = Expense(organization_id=actor.organization_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/expenses/categories", response_model=list[ExpenseCategoryRead])
def list_expense_categories(db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("read"))):
    return db.scalars(select(ExpenseCategory).where(ExpenseCategory.organization_id == actor.organization_id).order_by(ExpenseCategory.name)).all()


@router.get("/expenses/summary", response_model=ExpenseSummary)
def expense_summary(db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("read"))):
    expenses = db.scalars(select(Expense).where(Expense.organization_id == actor.organization_id).order_by(Expense.expense_date, Expense.created_at)).all()
    categories = {category.id: category.name for category in db.scalars(select(ExpenseCategory).where(ExpenseCategory.organization_id == actor.organization_id)).all()}
    total = sum((expense.amount for expense in expenses), start=0)
    by_category: defaultdict[str, object] = defaultdict(lambda: 0)
    monthly: defaultdict[str, object] = defaultdict(lambda: 0)
    for expense in expenses:
        by_category[categories.get(expense.category_id, "Uncategorized")] += expense.amount
        month = expense.expense_date.strftime("%Y-%m") if expense.expense_date else "unknown"
        monthly[month] += expense.amount
    return ExpenseSummary(
        total_spending=total,
        spending_by_category=dict(by_category),
        monthly_totals=dict(monthly),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/customers", response_model=list[CustomerRead])
def list_customers(db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("read"))):
    return db.scalars(select(Customer).where(Customer.organization_id == actor.organization_id)).all()


@router.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("accounting"))):
    item = Customer(organization_id=actor.organization_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/invoices", response_model=list[InvoiceRead])
def list_invoices(db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("read"))):
    return db.scalars(select(Invoice).where(Invoice.organization_id == actor.organization_id)).all()


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: UUID, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("read"))):
    item = _owned(db, Invoice, invoice_id, actor)
    return item


@router.post("/invoices", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("accounting"))):
    if db.scalar(select(Customer).where(Customer.id == payload.customer_id, Customer.organization_id == actor.organization_id)) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return create_invoice_service(db, payload, actor.organization_id)


@router.get("/accounting/summary", response_model=AccountingSummaryRead)
def accounting_summary(db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("accounting"))):
    return accounting_service.get_summary(db, actor.organization_id)


@router.get("/accounting/monthly-report", response_model=list[MonthlyReportEntryRead])
def accounting_monthly_report(db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("accounting"))):
    return accounting_service.get_monthly_report(db, actor.organization_id)


@router.get("/assistant/context")
def assistant_context(q: str, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("read"))) -> FinancialContext:
    return build_context(db, q, organization_id=actor.organization_id)


@router.get("/payments", response_model=list[PaymentRead])
def list_payments(db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("read"))):
    return db.scalars(select(Payment).where(Payment.organization_id == actor.organization_id)).all()


@router.post("/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment(payload: PaymentCreate, db: Session = Depends(get_db), actor: CurrentUser = Depends(require_permission("accounting"))):
    if db.scalar(select(Invoice).where(Invoice.id == payload.invoice_id, Invoice.organization_id == actor.organization_id)) is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    item = Payment(organization_id=actor.organization_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

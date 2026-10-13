from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.models.customer import Customer
from backend.app.models.expense import Expense
from backend.app.models.expense_category import ExpenseCategory
from backend.app.models.invoice import Invoice
from backend.app.models.payment import Payment
from backend.app.models.receipt import Receipt
from backend.app.schemas.accounting import AccountingSummaryRead, MonthlyReportEntryRead
from backend.app.schemas.customer import CustomerCreate, CustomerRead
from backend.app.schemas.expense import (
    ExpenseCategoryRead,
    ExpenseCreate,
    ExpenseRead,
    ExpenseSummary,
    ReceiptCreate,
    ReceiptRead,
)
from backend.app.schemas.invoice import InvoiceCreate, InvoiceRead
from backend.app.schemas.payment import PaymentCreate, PaymentRead
from backend.app.services import accounting as accounting_service
from backend.app.services.expense_pipeline import process_receipt
from backend.app.services.financial_query import FinancialContext, build_context
from backend.app.services.invoicing import create_invoice as create_invoice_service

router = APIRouter()


@router.post("/receipts", response_model=ReceiptRead, status_code=status.HTTP_201_CREATED)
def create_receipt(payload: ReceiptCreate, db: Session = Depends(get_db)):
    item = Receipt(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    process_receipt(db, item)
    db.refresh(item)
    return item


@router.post("/expenses", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db)):
    if db.get(Receipt, payload.receipt_id) is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if payload.category_id is not None and db.get(ExpenseCategory, payload.category_id) is None:
        raise HTTPException(status_code=404, detail="Expense category not found")
    item = Expense(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/expenses/categories", response_model=list[ExpenseCategoryRead])
def list_expense_categories(db: Session = Depends(get_db)):
    return db.scalars(select(ExpenseCategory).order_by(ExpenseCategory.name)).all()


@router.get("/expenses/summary", response_model=ExpenseSummary)
def expense_summary(db: Session = Depends(get_db)):
    expenses = db.scalars(select(Expense).order_by(Expense.expense_date, Expense.created_at)).all()
    categories = {category.id: category.name for category in db.scalars(select(ExpenseCategory)).all()}
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
    if db.get(Customer, payload.customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return create_invoice_service(db, payload)


@router.get("/accounting/summary", response_model=AccountingSummaryRead)
def accounting_summary(db: Session = Depends(get_db)):
    return accounting_service.get_summary(db)


@router.get("/accounting/monthly-report", response_model=list[MonthlyReportEntryRead])
def accounting_monthly_report(db: Session = Depends(get_db)):
    return accounting_service.get_monthly_report(db)


@router.get("/assistant/context")
def assistant_context(q: str, db: Session = Depends(get_db)) -> FinancialContext:
    return build_context(db, q)


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

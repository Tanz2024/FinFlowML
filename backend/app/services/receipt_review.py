from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.expense import Expense
from backend.app.models.receipt import Receipt
from backend.app.models.receipt_status import VALID_TRANSITIONS, ReceiptStatus
from backend.app.services.category_matcher import categorize_merchant
from backend.app.services.currency import normalize_currency

FIELDS = ("company", "receipt_date", "address", "total", "currency")


def effective_data(receipt: Receipt) -> dict:
    data = dict(receipt.raw_extracted_data or receipt.extracted_data or {})
    data.update(receipt.corrected_data or {})
    data.setdefault("company", receipt.company)
    data.setdefault("receipt_date", receipt.receipt_date.isoformat() if receipt.receipt_date else None)
    data.setdefault("address", receipt.address)
    data.setdefault("total", str(receipt.total) if receipt.total is not None else None)
    data.setdefault("currency", receipt.currency)
    return data


def validate_receipt_data(data: dict) -> list[str]:
    errors = []
    if not str(data.get("company") or "").strip():
        errors.append("company is required")
    if not str(data.get("currency") or "").strip().isalpha() or len(str(data.get("currency") or "")) != 3:
        errors.append("currency must be a three-letter code")
    if not str(data.get("address") or "").strip():
        errors.append("address is required")
    try:
        amount = Decimal(str(data.get("total")))
        if amount <= 0:
            errors.append("total must be greater than zero")
    except (InvalidOperation, TypeError):
        errors.append("total must be a valid amount")
    try:
        parsed = date.fromisoformat(str(data.get("receipt_date")))
        if parsed > date.today():
            errors.append("receipt_date cannot be in the future")
    except (TypeError, ValueError):
        errors.append("receipt_date must be an ISO date")
    return errors


def transition(receipt: Receipt, target: ReceiptStatus) -> None:
    current = ReceiptStatus(receipt.status)
    if target not in VALID_TRANSITIONS[current]:
        raise HTTPException(status_code=409, detail=f"invalid receipt transition: {current} -> {target}")
    receipt.status = target.value


def store_extraction(db: Session, receipt: Receipt) -> Receipt:
    transition(receipt, ReceiptStatus.PROCESSING)
    raw = {
        key: value.isoformat() if hasattr(value, "isoformat") else str(value) if isinstance(value, Decimal) else value
        for key, value in (receipt.extracted_data or {}).items()
    }
    raw.update({field: getattr(receipt, field) for field in FIELDS if getattr(receipt, field) is not None})
    raw = {
        key: value.isoformat() if hasattr(value, "isoformat") else str(value) if isinstance(value, Decimal) else value
        for key, value in raw.items()
    }
    receipt.raw_extracted_data = raw
    receipt.validation_errors = validate_receipt_data(effective_data(receipt))
    transition(receipt, ReceiptStatus.NEEDS_REVIEW)
    db.commit()
    db.refresh(receipt)
    return receipt


def approve_receipt(db: Session, receipt: Receipt) -> Expense:
    if receipt.status == ReceiptStatus.APPROVED:
        existing = db.scalar(select(Expense).where(Expense.receipt_id == receipt.id))
        if existing is None:
            raise HTTPException(status_code=409, detail="approved receipt has no expense")
        return existing
    if receipt.status != ReceiptStatus.NEEDS_REVIEW:
        raise HTTPException(status_code=409, detail="only receipts needing review can be approved")
    data = effective_data(receipt)
    errors = validate_receipt_data(data)
    receipt.validation_errors = errors
    if errors:
        db.commit()
        raise HTTPException(status_code=422, detail={"validation_errors": errors})
    try:
        existing = db.scalar(select(Expense).where(Expense.receipt_id == receipt.id))
        if existing is None:
            category = categorize_merchant(db, data["company"])
            existing = Expense(
                receipt_id=receipt.id,
                category_id=category.id,
                merchant_name=data["company"],
                expense_date=date.fromisoformat(str(data["receipt_date"])),
                amount=Decimal(str(data["total"])),
                currency=normalize_currency(data["currency"]),
            )
            db.add(existing)
        receipt.status = ReceiptStatus.APPROVED.value
        receipt.validation_errors = []
        db.commit()
        db.refresh(existing)
        return existing
    except SQLAlchemyError:
        db.rollback()
        raise


def reject_receipt(db: Session, receipt: Receipt) -> Receipt:
    if receipt.status == ReceiptStatus.REJECTED.value:
        return receipt
    transition(receipt, ReceiptStatus.REJECTED)
    db.commit()
    db.refresh(receipt)
    return receipt

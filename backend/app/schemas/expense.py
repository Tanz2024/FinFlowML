from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReceiptCreate(BaseModel):
    extracted_data: dict[str, str | None] = Field(default_factory=dict)
    ocr_text: str | None = None
    image_reference: str | None = None
    source_filename: str | None = None
    company: str | None = None
    receipt_date: date | None = None
    address: str | None = None
    total: Decimal | None = Field(default=None, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class ReceiptRead(ReceiptCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    created_at: datetime
    raw_extracted_data: dict | None = None
    corrected_data: dict | None = None
    validation_errors: list[str] | None = None


class ReceiptCorrection(BaseModel):
    corrections: dict[str, str | None] = Field(default_factory=dict)


class ReceiptStatusRead(BaseModel):
    id: UUID
    status: str
    validation_errors: list[str] | None = None
    effective_data: dict
    expense_id: UUID | None = None


class ReviewFieldRead(BaseModel):
    original_model_value: str | None = None
    normalized_value: str | None = None
    reviewer_corrected_value: str | None = None
    effective_value: str | None = None
    status: str
    errors: list[str] = Field(default_factory=list)


class ReceiptReviewRead(BaseModel):
    receipt_id: UUID
    status: str
    fields: dict[str, ReviewFieldRead]
    validation_errors: list[str] = Field(default_factory=list)


class ExpenseCreate(BaseModel):
    receipt_id: UUID
    category_id: UUID | None = None
    amount: Decimal = Field(decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    merchant_name: str | None = None
    expense_date: date | None = None
    notes: str | None = None


class ExpenseRead(ExpenseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class ExpenseCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    is_system: bool


class ExpenseSummary(BaseModel):
    total_spending: Decimal | None
    spending_by_category: dict[str, Decimal]
    monthly_totals: dict[str, Decimal]
    currency_totals: dict[str, Decimal] = Field(default_factory=dict)
    spending_by_currency_and_category: dict[str, dict[str, Decimal]] = Field(default_factory=dict)
    monthly_totals_by_currency: dict[str, dict[str, Decimal]] = Field(default_factory=dict)

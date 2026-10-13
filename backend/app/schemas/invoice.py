from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InvoiceItemCreate(BaseModel):
    description: str
    quantity: Decimal = Field(default=Decimal("1"), decimal_places=2)
    unit_price: Decimal = Field(decimal_places=2)
    amount: Decimal = Field(decimal_places=2)


class InvoiceItemRead(InvoiceItemCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class InvoiceCreate(BaseModel):
    customer_id: UUID
    invoice_number: str
    invoice_date: date
    due_date: date
    subtotal: Decimal = Field(decimal_places=2)
    tax: Decimal = Field(decimal_places=2)
    total: Decimal = Field(decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    status: str = "unpaid"
    source_filename: str | None = None
    items: list[InvoiceItemCreate] = Field(default_factory=list)


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    customer_id: UUID
    invoice_number: str
    invoice_date: date
    due_date: date
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    currency: str
    status: str
    source_filename: str | None
    created_at: datetime
    items: list[InvoiceItemRead] = Field(default_factory=list)

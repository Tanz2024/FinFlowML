from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InvoiceCreate(BaseModel):
    customer_id: UUID
    invoice_number: str
    invoice_date: date
    due_date: date
    subtotal: Decimal = Field(decimal_places=2)
    tax: Decimal = Field(decimal_places=2)
    total: Decimal = Field(decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    status: str
    source_filename: str | None = None


class InvoiceRead(InvoiceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime

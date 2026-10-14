from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InvoiceItemCreate(BaseModel):
    description: str
    quantity: Decimal = Field(default=Decimal("1"), decimal_places=2)
    unit_price: Decimal = Field(decimal_places=2)
    amount: Decimal = Field(decimal_places=2)

    @model_validator(mode="after")
    def validate_amount(self):
        expected = (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        if self.quantity <= 0 or self.unit_price < 0 or self.amount != expected:
            raise ValueError("line amount must equal quantity × unit price")
        return self


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

    @model_validator(mode="after")
    def validate_totals(self):
        if self.subtotal < 0 or self.tax < 0 or self.total < 0:
            raise ValueError("invoice amounts cannot be negative")
        if self.items:
            item_total = sum((item.amount for item in self.items), start=Decimal("0.00"))
            if item_total != self.subtotal:
                raise ValueError("subtotal must equal the sum of line items")
        if self.total != (self.subtotal + self.tax).quantize(Decimal("0.01")):
            raise ValueError("total must equal subtotal plus tax")
        if self.due_date < self.invoice_date:
            raise ValueError("due date cannot precede invoice date")
        return self


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

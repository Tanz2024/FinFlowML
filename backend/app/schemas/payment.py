from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    invoice_id: UUID
    payment_date: date
    amount_paid: Decimal = Field(decimal_places=2)


class PaymentRead(PaymentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    name: str


class CustomerRead(CustomerCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime

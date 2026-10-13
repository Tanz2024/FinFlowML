from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.registry import Base


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (UniqueConstraint("receipt_id", name="uq_expenses_receipt_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=True)
    receipt_id: Mapped[UUID] = mapped_column(ForeignKey("receipts.id"), index=True)
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("expense_categories.id"), index=True, nullable=True
    )
    merchant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expense_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    receipt: Mapped["Receipt"] = relationship(back_populates="expenses")
    category: Mapped["ExpenseCategory | None"] = relationship(back_populates="expenses")

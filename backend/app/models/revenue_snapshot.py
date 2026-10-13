from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.registry import Base


class RevenueSnapshot(Base):
    """A single time-series point of realized revenue, for forecasting input."""

    __tablename__ = "revenue_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    period: Mapped[date] = mapped_column(Date, index=True)
    period_granularity: Mapped[str] = mapped_column(String(20), default="monthly")
    revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

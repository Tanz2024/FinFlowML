"""add revenue snapshots for forecasting"""

import sqlalchemy as sa
from alembic import op

revision = "0004_revenue_snapshots"
down_revision = "0003_invoice_accounting"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "revenue_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("period_granularity", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("revenue", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revenue_snapshots_period", "revenue_snapshots", ["period"])


def downgrade():
    op.drop_index("ix_revenue_snapshots_period", table_name="revenue_snapshots")
    op.drop_table("revenue_snapshots")

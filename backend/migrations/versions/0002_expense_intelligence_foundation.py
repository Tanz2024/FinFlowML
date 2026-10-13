"""add receipt and expense intelligence foundation"""

import sqlalchemy as sa
from alembic import op

revision = "0002_expense_intelligence_foundation"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_filename", sa.String(255)),
        sa.Column("image_reference", sa.String(500)),
        sa.Column("ocr_text", sa.Text()),
        sa.Column("extracted_data", sa.JSON()),
        sa.Column("company", sa.String(255)),
        sa.Column("receipt_date", sa.Date()),
        sa.Column("address", sa.Text()),
        sa.Column("total", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3)),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("receipt_id", sa.Uuid(), sa.ForeignKey("receipts.id"), nullable=False),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("expense_categories.id")),
        sa.Column("merchant_name", sa.String(255)),
        sa.Column("expense_date", sa.Date()),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_expenses_receipt_id", "expenses", ["receipt_id"])
    op.create_index("ix_expenses_category_id", "expenses", ["category_id"])


def downgrade():
    op.drop_index("ix_expenses_category_id", table_name="expenses")
    op.drop_index("ix_expenses_receipt_id", table_name="expenses")
    op.drop_table("expenses")
    op.drop_table("expense_categories")
    op.drop_table("receipts")

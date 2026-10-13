"""add organizations, users, memberships, and tenant keys"""

import sqlalchemy as sa
from alembic import op

revision = "0006_auth_and_tenants"
down_revision = "0005_receipt_review_workflow"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("organizations", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("name", sa.String(255), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("users", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("email", sa.String(320), nullable=False, unique=True), sa.Column("password_hash", sa.String(512), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("organization_memberships", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False), sa.Column("role", sa.String(30), nullable=False))
    for table in ("customers", "invoices", "payments", "receipts", "expenses", "expense_categories"):
        op.add_column(table, sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=True))
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
    op.create_unique_constraint("uq_expenses_receipt_id", "expenses", ["receipt_id"])
    # Existing records remain quarantined: no user is created or granted access.
    # A deployment must explicitly create an organization and assign these rows.


def downgrade():
    op.drop_constraint("uq_expenses_receipt_id", "expenses", type_="unique")
    for table in ("expense_categories", "expenses", "receipts", "payments", "invoices", "customers"):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_column(table, "organization_id")
    op.drop_table("organization_memberships")
    op.drop_table("users")
    op.drop_table("organizations")

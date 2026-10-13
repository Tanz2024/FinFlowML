"""Make expense categories unique within, rather than across, organizations."""

from alembic import op

revision = "0010_tenant_category"
down_revision = "0009_extraction_fencing"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("expense_categories_name_key", "expense_categories", type_="unique")
    op.create_unique_constraint("uq_expense_categories_org_name", "expense_categories", ["organization_id", "name"])


def downgrade():
    op.drop_constraint("uq_expense_categories_org_name", "expense_categories", type_="unique")
    op.create_unique_constraint("expense_categories_name_key", "expense_categories", ["name"])

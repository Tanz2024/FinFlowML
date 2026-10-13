"""Record the authenticated actor for receipt review actions."""

import sqlalchemy as sa
from alembic import op

revision = "0007_receipt_review_actors"
down_revision = "0006_auth_and_tenants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("last_action_by_user_id", "corrected_by_user_id", "approved_by_user_id", "rejected_by_user_id"):
        op.add_column("receipts", sa.Column(name, sa.Uuid(), nullable=True))
        op.create_foreign_key(f"fk_receipts_{name}", "receipts", "users", [name], ["id"])


def downgrade() -> None:
    for name in ("rejected_by_user_id", "approved_by_user_id", "corrected_by_user_id", "last_action_by_user_id"):
        op.drop_constraint(f"fk_receipts_{name}", "receipts", type_="foreignkey")
        op.drop_column("receipts", name)

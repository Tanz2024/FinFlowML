"""add human review fields to receipts"""

import sqlalchemy as sa
from alembic import op

revision = "0005_receipt_review_workflow"
down_revision = "0004_revenue_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("receipts", sa.Column("raw_extracted_data", sa.JSON(), nullable=True))
    op.add_column("receipts", sa.Column("corrected_data", sa.JSON(), nullable=True))
    op.add_column("receipts", sa.Column("validation_errors", sa.JSON(), nullable=True))
    op.execute("UPDATE receipts SET status = 'needs_review' WHERE status IN ('extracted', 'processed')")


def downgrade():
    op.drop_column("receipts", "validation_errors")
    op.drop_column("receipts", "corrected_data")
    op.drop_column("receipts", "raw_extracted_data")

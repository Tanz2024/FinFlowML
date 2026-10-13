"""Add payload identity and lease fencing to extraction jobs."""

import sqlalchemy as sa
from alembic import op

revision = "0009_extraction_fencing"
down_revision = "0008_extraction_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("extraction_jobs", sa.Column("payload_hash", sa.String(64), nullable=True))
    op.add_column("extraction_jobs", sa.Column("lease_owner", sa.String(64), nullable=True))
    op.add_column("extraction_jobs", sa.Column("fence", sa.Integer(), nullable=False, server_default="0"))
    # Existing jobs predate payload identity. They are retained, but new API submissions
    # require a hash and cannot reuse an ambiguous legacy idempotency key.


def downgrade():
    op.drop_column("extraction_jobs", "fence")
    op.drop_column("extraction_jobs", "lease_owner")
    op.drop_column("extraction_jobs", "payload_hash")

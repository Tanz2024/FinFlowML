"""Add durable, tenant-scoped extraction jobs."""

import sqlalchemy as sa
from alembic import op

revision = "0008_extraction_jobs"
down_revision = "0007_receipt_review_actors"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "extraction_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), sa.ForeignKey("receipts.id"), nullable=False, unique=True),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("model_id", sa.String(255)),
        sa.Column("model_revision", sa.String(255)),
        sa.Column("adapter_fingerprint", sa.String(128)),
        sa.Column("worker_version", sa.String(100)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_extraction_job_idempotency"),
    )
    op.create_index("ix_extraction_jobs_organization_id", "extraction_jobs", ["organization_id"])


def downgrade():
    op.drop_index("ix_extraction_jobs_organization_id", table_name="extraction_jobs")
    op.drop_table("extraction_jobs")

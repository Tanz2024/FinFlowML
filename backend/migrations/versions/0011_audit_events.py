"""Add tenant-scoped append-only audit events."""

import sqlalchemy as sa
from alembic import op

revision = "0011_audit_events"
down_revision = "0010_tenant_category"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Uuid()),
        sa.Column("correlation_id", sa.String(80)),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("model_id", sa.String(255)),
        sa.Column("model_revision", sa.String(255)),
        sa.Column("adapter_fingerprint", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])
    op.create_index("ix_audit_events_org_time", "audit_events", ["organization_id", "created_at"])


def downgrade():
    op.drop_index("ix_audit_events_org_time", table_name="audit_events")
    op.drop_index("ix_audit_events_organization_id", table_name="audit_events")
    op.drop_table("audit_events")

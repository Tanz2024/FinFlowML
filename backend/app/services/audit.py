"""Append-only application audit events with deliberate redaction boundaries."""

from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.audit_event import AuditEvent


def record_event(
    db: Session,
    organization_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    *,
    actor_id: UUID | None = None,
    correlation_id: str | None = None,
    details: dict | None = None,
    model_id: str | None = None,
    model_revision: str | None = None,
    adapter_fingerprint: str | None = None,
) -> AuditEvent:
    safe = {key: value for key, value in (details or {}).items() if key not in {"password", "token", "ocr_text", "image", "raw_output"}}
    event = AuditEvent(organization_id=organization_id, actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, correlation_id=correlation_id, details=safe, model_id=model_id, model_revision=model_revision, adapter_fingerprint=adapter_fingerprint)
    db.add(event)
    return event

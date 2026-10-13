from sqlalchemy import select

from backend.app.models.audit_event import AuditEvent
from backend.app.services.audit import record_event
from backend.app.services.extraction_jobs import claim_next, process_job


def test_audit_events_are_redacted_and_tenant_scoped(client, client_db, monkeypatch):
    import backend.app.demo as demo
    monkeypatch.setenv("FINFLOW_MOCK_EXTRACTION", "true")
    monkeypatch.setattr(demo, "_uploaded_file", lambda body, content_type: ("receipt.jpg", b"audit"))
    client.post("/predict", files={"receipt": ("receipt.jpg", b"x", "image/jpeg")}, headers={"Idempotency-Key": "audit-1"})
    claimed = claim_next(client_db)
    process_job(client_db, claimed.id, claimed.lease_owner, claimed.fence)
    event = client_db.scalar(select(AuditEvent).where(AuditEvent.action == "extraction.completed"))
    assert event is not None
    assert event.actor_id is None
    assert "token" not in event.details
    assert client.get("/admin/audit-events").status_code == 200


def test_audit_event_api_redacts_sensitive_details(client_db):
    organization_id = client_db.info["test_organization_id"]
    record_event(client_db, organization_id, "test.redaction", "test", details={"password": "secret", "token": "secret", "safe": "yes"})
    client_db.commit()
    event = client_db.scalar(select(AuditEvent).where(AuditEvent.action == "test.redaction"))
    assert event.details == {"safe": "yes"}

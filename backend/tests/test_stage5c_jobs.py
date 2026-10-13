from uuid import UUID

from backend.app.models.extraction_job import ExtractionJob
from backend.app.services.extraction_jobs import claim_next, process_job


def test_authenticated_upload_worker_completion_and_review(client, client_db, monkeypatch):
    monkeypatch.setenv("FINFLOW_MOCK_EXTRACTION", "true")
    import backend.app.demo as demo
    monkeypatch.setattr(demo, "_uploaded_file", lambda body, content_type: ("receipt.jpg", b"durable image"))
    response = client.post(
        "/predict", files={"receipt": ("receipt.jpg", b"ignored", "image/jpeg")}, headers={"Idempotency-Key": "job-e2e-1"}
    )
    assert response.status_code == 202
    payload = response.json()
    job = client_db.get(ExtractionJob, UUID(payload["job_id"]))
    claimed = claim_next(client_db)
    assert claimed and claimed.id == job.id
    process_job(client_db, claimed.id, claimed.lease_owner, claimed.fence)
    status = client.get(f"/jobs/{job.id}")
    assert status.json()["state"] == "completed"
    assert client.get(f"/receipts/{payload['receipt_id']}").json()["status"] == "needs_review"
    correction = client.patch(f"/receipts/{payload['receipt_id']}/corrections", json={"corrections": {"receipt_date": "2025-01-15"}})
    assert correction.status_code == 200
    assert "date" not in correction.json().get("corrected_data", {})
    assert correction.json()["corrected_data"]["receipt_date"] == "2025-01-15"
    assert client.post(f"/receipts/{payload['receipt_id']}/approve").status_code == 200


def test_duplicate_submission_reuses_job(client, monkeypatch):
    import backend.app.demo as demo
    monkeypatch.setattr(demo, "_uploaded_file", lambda body, content_type: ("receipt.jpg", b"same image"))
    headers = {"Idempotency-Key": "duplicate-1"}
    files = {"receipt": ("receipt.jpg", b"ignored", "image/jpeg")}
    first = client.post("/predict", files=files, headers=headers).json()
    second = client.post("/predict", files=files, headers=headers).json()
    assert first["job_id"] == second["job_id"]


def test_idempotency_key_rejects_different_content(client, monkeypatch):
    import backend.app.demo as demo
    monkeypatch.setattr(demo, "_uploaded_file", lambda body, content_type: ("receipt.jpg", body))
    headers = {"Idempotency-Key": "different-content-1"}
    assert client.post("/predict", files={"receipt": ("receipt.jpg", b"one", "image/jpeg")}, headers=headers).status_code == 202
    response = client.post("/predict", files={"receipt": ("receipt.jpg", b"two", "image/jpeg")}, headers=headers)
    assert response.status_code == 409


def test_stale_fenced_worker_cannot_complete_new_lease(client, client_db, monkeypatch):
    import backend.app.demo as demo
    from backend.app.services.extraction_jobs import claim_next, process_job, reclaim_stale
    monkeypatch.setenv("FINFLOW_MOCK_EXTRACTION", "true")
    monkeypatch.setattr(demo, "_uploaded_file", lambda body, content_type: ("receipt.jpg", b"fenced"))
    payload = client.post("/predict", files={"receipt": ("receipt.jpg", b"ignored", "image/jpeg")}, headers={"Idempotency-Key": "fence-1"}).json()
    first = claim_next(client_db)
    stale_owner, stale_fence = first.lease_owner, first.fence
    first.lease_until = first.lease_until.replace(year=first.lease_until.year - 1)
    client_db.commit()
    reclaim_stale(client_db)
    second = claim_next(client_db)
    assert second.fence > stale_fence
    result = process_job(client_db, second.id, stale_owner, stale_fence)
    assert result.state == "processing"
    assert payload["job_id"]


def test_unauthorized_job_access_is_rejected(client):
    response = client.get("/jobs/00000000-0000-0000-0000-000000000000", headers={"Authorization": "Bearer bad"})
    assert response.status_code == 401

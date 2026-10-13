from uuid import UUID

from backend.app.models.extraction_job import ExtractionJob
from backend.app.services.extraction_jobs import process_job


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
    process_job(client_db, job.id)
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


def test_unauthorized_job_access_is_rejected(client):
    response = client.get("/jobs/00000000-0000-0000-0000-000000000000", headers={"Authorization": "Bearer bad"})
    assert response.status_code == 401

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


def test_model_extraction_keeps_raw_values_and_reviews_normalized_values(client, client_db, monkeypatch):
    import backend.app.demo as demo
    import ml.inference.predict as inference

    monkeypatch.setattr(demo, "_uploaded_file", lambda body, content_type: ("receipt.jpg", b"normalized"))
    monkeypatch.setattr(inference, "predict_image", lambda *args, **kwargs: (
        "OCR", "{}", {"company": "  OJC   MARKETING SDN BHD ", "date": "15/01/201911:05:16AM", "address": "A  Road\nJohor", "total": "RM 193", "currency": "MYR"}, None,
    ))
    payload = client.post("/predict", files={"receipt": ("receipt.jpg", b"ignored", "image/jpeg")}, headers={"Idempotency-Key": "normalize-1"}).json()
    claimed = claim_next(client_db)
    process_job(client_db, claimed.id, claimed.lease_owner, claimed.fence)
    receipt = client.get(f"/receipts/{payload['receipt_id']}").json()
    assert receipt["extracted_data"]["date"] == "2019-01-15"
    assert receipt["extracted_data"]["address"] == "a road johor"
    assert receipt["extracted_data"]["total"] == "193.00"
    assert receipt["raw_extracted_data"]["date"] == "15/01/201911:05:16AM"
    assert receipt["status"] == "needs_review"


def test_four_field_model_prediction_detects_currency_from_total(client, client_db, monkeypatch):
    import backend.app.demo as demo
    import ml.inference.predict as inference

    monkeypatch.setattr(demo, "_uploaded_file", lambda body, content_type: ("receipt.jpg", b"colab-shape"))
    monkeypatch.setattr(inference, "predict_image", lambda *args, **kwargs: (
        "DEMO CAFE SDN BHD\n15/10/2026\n123 TEST ROAD KUALA LUMPUR\nTOTAL MYR 12.50",
        "{}",
        {"company": "DEMO CAFE SDN BHD", "date": "15/10/2026", "address": "123 TEST ROAD KUALA LUMPUR", "total": "MYR 12.50"},
        None,
    ))
    payload = client.post("/predict", files={"receipt": ("receipt.jpg", b"ignored", "image/jpeg")}, headers={"Idempotency-Key": "colab-shape-1"}).json()
    claimed = claim_next(client_db)
    process_job(client_db, claimed.id, claimed.lease_owner, claimed.fence)
    receipt = client.get(f"/receipts/{payload['receipt_id']}").json()
    assert receipt["extracted_data"] == {
        "company": "demo cafe sdn bhd", "date": "2026-10-15",
        "address": "123 test road kuala lumpur", "total": "12.50", "currency": "MYR",
    }
    assert receipt["raw_extracted_data"]["total"] == "MYR 12.50"
    assert receipt["status"] == "needs_review"


def test_currency_conflict_between_model_and_ocr_requires_review(client, client_db, monkeypatch):
    import backend.app.demo as demo
    import ml.inference.predict as inference

    monkeypatch.setattr(demo, "_uploaded_file", lambda body, content_type: ("receipt.jpg", b"currency-conflict"))
    monkeypatch.setattr(inference, "predict_image", lambda *args, **kwargs: (
        "TOTAL USD 12.50", "{}",
        {"company": "Cafe", "date": "15/10/2026", "address": "Road", "total": "MYR 12.50", "currency": "MYR"}, None,
    ))
    payload = client.post("/predict", files={"receipt": ("receipt.jpg", b"ignored", "image/jpeg")}, headers={"Idempotency-Key": "currency-conflict-1"}).json()
    claimed = claim_next(client_db)
    process_job(client_db, claimed.id, claimed.lease_owner, claimed.fence)
    receipt = client.get(f"/receipts/{payload['receipt_id']}").json()
    assert receipt["raw_extracted_data"]["currency"] == "MYR"
    assert receipt["extracted_data"]["currency"] is None
    assert receipt["status"] == "needs_review"


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

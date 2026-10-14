def test_demo_page(client):
    response = client.get("/demo")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "Extract Receipt Data" in response.text
    assert "Save Corrections" in response.text
    assert "Original model" in response.text
    assert "Approve and create expense" in response.text
    assert "const all=corrections(),changed={}" in response.text
    assert "Save corrections before approving." in response.text
    assert "URL.revokeObjectURL(imageUrl)" in response.text


def test_health_and_readiness_are_available(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


def test_predict_upload_uses_stage5_pipeline(client, monkeypatch):
    import backend.app.demo as demo

    monkeypatch.setattr(demo, "_uploaded_file", lambda body, content_type: ("receipt.jpg", b"valid image"))
    response = client.post(
        "/predict",
        files={"receipt": ("receipt.jpg", b"fake image", "image/jpeg")},
        headers={"Idempotency-Key": "demo-test-1"},
    )
    assert response.status_code == 202
    assert response.json()["state"] == "queued"
    assert "job_id" in response.json()


def test_predict_requires_image(client):
    response = client.post("/predict", json={})
    assert response.status_code == 415


def test_uploaded_receipt_image_is_authenticated_and_tenant_scoped(client, monkeypatch):
    import backend.app.demo as demo

    monkeypatch.setattr(demo, "_uploaded_file", lambda body, content_type: ("receipt.jpg", b"image bytes"))
    response = client.post(
        "/predict", files={"receipt": ("receipt.jpg", b"fake image", "image/jpeg")}, headers={"Idempotency-Key": "image-route-1"}
    )
    receipt_id = response.json()["receipt_id"]
    image = client.get(f"/receipts/{receipt_id}/image")
    assert image.status_code == 200
    assert image.content == b"image bytes"

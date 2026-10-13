def test_demo_page(client):
    response = client.get("/demo")
    assert response.status_code == 200
    assert "Extract Receipt Data" in response.text


def test_predict_upload_uses_stage5_pipeline(client, monkeypatch):
    import backend.app.demo as demo

    monkeypatch.setattr(
        demo,
        "predict_image",
        lambda image, base, adapter: (
            "OCR text",
            "raw output",
            {"company": "Shop", "date": "2025-01-01", "address": "Road", "total": "10.00"},
            None,
        ),
    )
    response = client.post(
        "/predict",
        files={"receipt": ("receipt.jpg", b"fake image", "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["total"] == "10.00"


def test_predict_requires_image(client):
    response = client.post("/predict", json={})
    assert response.status_code == 415

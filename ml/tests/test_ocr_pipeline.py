import pytest

from ml.ocr import extract_text
from ml.ocr.extract import OCRExtractionError


def test_ocr_module_imports():
    assert callable(extract_text)


def test_ocr_rejects_invalid_image_path(tmp_path):
    with pytest.raises(OCRExtractionError, match="does not exist"):
        extract_text(tmp_path / "missing.jpg")


def test_end_to_end_image_pipeline_is_mockable(tmp_path, monkeypatch):
    image = tmp_path / "receipt.jpg"
    image.write_bytes(b"image")
    import ml.inference.predict as inference

    monkeypatch.setattr(inference, "extract_text", lambda path: "TOTAL 10.80")
    monkeypatch.setattr(inference, "predict", lambda text, base, adapter, max_new_tokens: (
        '{"company": null, "date": null, "address": null, "total": "10.80"}',
        {"company": None, "date": None, "address": None, "total": "10.80"},
        None,
    ))

    result = inference.predict_image(str(image), "base-model", "adapter", max_new_tokens=8)

    assert result[0] == "TOTAL 10.80"
    assert result[2]["total"] == "10.80"
    assert result[3] is None


def test_missing_image_cli_prints_guidance():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "ml.inference.predict", "--image", "sample_receipt.jpg"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Receipt image not found: sample_receipt.jpg" in result.stdout
    assert "Please provide a valid image path." in result.stdout

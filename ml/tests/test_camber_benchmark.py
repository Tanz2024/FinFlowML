import json
import sys
from pathlib import Path

import scripts.camber_receipt_benchmark as benchmark


def _manifest(tmp_path: Path) -> Path:
    image = tmp_path / "receipt.png"
    image.write_bytes(b"synthetic")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{
        "image": str(image),
        "expected": {"company": "Demo Cafe", "date": "15/10/2026",
                      "address": "123 Test Road", "total": "MYR 12.50"},
    }]))
    return manifest


def _run(monkeypatch, tmp_path, prediction, ocr="COMPANY Demo Cafe"):
    manifest = _manifest(tmp_path)
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}")
    output = tmp_path / "output"
    loads = []
    monkeypatch.setattr(benchmark.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(benchmark.torch.cuda, "reset_peak_memory_stats", lambda: None)
    monkeypatch.setattr(benchmark.torch.cuda, "max_memory_allocated", lambda: 123)
    monkeypatch.setattr(benchmark, "build_quantization_config", lambda: object())
    monkeypatch.setattr(benchmark, "load_inference_model", lambda *args, **kwargs: loads.append(object()) or loads[-1])
    monkeypatch.setattr(benchmark, "extract_text", ocr if callable(ocr) else lambda _: ocr)
    monkeypatch.setattr(benchmark, "generate_prediction", lambda *args, **kwargs: ("raw private", prediction, None if prediction else "malformed"))
    monkeypatch.setattr(sys, "argv", ["benchmark", "--manifest", str(manifest), "--adapter", str(adapter), "--output-dir", str(output)])
    assert benchmark.main() == 0
    return json.loads((output / "results.json").read_text()), (output / "results.csv").read_text(), loads


def test_benchmark_uses_normalized_four_field_accuracy_and_reuses_model(monkeypatch, tmp_path):
    result, csv_text, loads = _run(monkeypatch, tmp_path, {
        "company": " demo   cafe ", "date": "2026-10-15", "address": "123 Test Road", "total": "12.5",
    })
    assert result["field_correct"] == {"company": 1, "date": 1, "address": 1, "total": 1}
    assert result["all_fields_correct"] == 1
    assert result["peak_vram_bytes"] == 123
    assert len(loads) == 1
    assert "raw private" not in csv_text
    assert "Demo Cafe" not in csv_text


def test_benchmark_exports_failed_receipt_with_stable_csv_columns(monkeypatch, tmp_path):
    result, csv_text, _ = _run(monkeypatch, tmp_path, None)
    assert result["json_valid"] == 0
    assert result["parsing_errors"] == 1
    assert "company_correct" in csv_text
    assert "error_type" in csv_text


def test_manifest_validation_precedes_cuda(tmp_path):
    missing = tmp_path / "missing.json"
    try:
        benchmark._load_manifest(missing)
    except ValueError as exc:
        assert "manifest does not exist" in str(exc)
    else:
        raise AssertionError("missing manifest was accepted")


def test_benchmark_sanitizes_ocr_failure(monkeypatch, tmp_path):
    def fail(_):
        raise ValueError("private OCR details")

    result, csv_text, _ = _run(monkeypatch, tmp_path, None, fail)
    assert result["records"][0]["error_type"] == "ValueError"
    assert "private OCR details" not in csv_text

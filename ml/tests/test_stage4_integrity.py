import json

import pytest

from ml.data.sroie import words_to_text
from ml.evaluation.metrics import metrics
from ml.evaluation.stage4_adapter_benchmark import _load_checkpoint, _near_duplicate_report
from ml.evaluation.verify_stage4_artifacts import verify_artifacts
from ml.extraction.schema import ExtractionExample


def _record(index: int, label: str) -> dict:
    score = {
        "normalized_exact_match": {field: True for field in ("company", "date", "address", "total")},
        "macro_field_accuracy": 1.0,
        "document_all_fields_correct": True,
    }
    return {
        "example_id": f"test:{index}",
        "fingerprint": f"fp-{index}",
        "invalid_output": False,
        "scores": score,
        "model_label": label,
    }


def test_words_to_text_and_example_id_handle_null_tokens():
    assert words_to_text(["ACME", None, 12]) == "ACME 12"
    example = ExtractionExample("test", 2, "fp", {}, {}, False, (), "test:2")
    assert example.example_id == "test:2"


def test_dataset_integrity_reports_exact_and_near_target_overlap():
    Item = type("Item", (), {})
    train = Item()
    train.example_id, train.fingerprint, train.raw_targets = "train:0", "same", {"company": "ACME", "date": None}
    test = Item()
    test.example_id, test.fingerprint, test.raw_targets = "test:0", "same", {"company": "ACME", "date": None}
    result = _near_duplicate_report({"train": [train], "validation": [], "test": [test]})
    assert result["exact_fingerprint_overlap"]["train_vs_test"] == ["same"]
    assert result["near_target_text_overlap_ge_0.98"]["train_vs_test"]


def test_missing_fields_are_not_scored_as_correct():
    expected = {"company": "ACME", "date": None, "address": "A Road", "total": "1.00"}
    predicted = {"company": "ACME", "date": None, "address": "A Road"}
    result = metrics(expected, predicted)
    assert result["normalized_exact_match"]["date"] is False
    assert result["normalized_exact_match"]["total"] is False
    assert result["valid_structured_output"] is False


def test_resume_checkpoint_rejects_manifest_or_identity_mismatch(tmp_path):
    path = tmp_path / "base.partial.json"
    manifest = {"documents": ["test:0"], "prompt": "p"}
    path.write_text(json.dumps({"manifest": manifest, "records": [_record(0, "base")]}) + "\n")
    assert _load_checkpoint(path, manifest, True)[0]["example_id"] == "test:0"
    with pytest.raises(ValueError, match="manifest mismatch"):
        _load_checkpoint(path, {"documents": ["test:1"], "prompt": "p"}, True)


def test_verify_stage4_artifacts_reconciles_report_and_predictions(tmp_path):
    records = [_record(0, "base")]
    adapter_records = [_record(0, "adapter")]
    summary = {
        "model_label": "base",
        "documents": 1,
        "json_validity_rate": 1.0,
        "field_accuracy": {field: 1.0 for field in ("company", "date", "address", "total")},
        "macro_field_accuracy": 1.0,
        "all_fields_correct_rate": 1.0,
    }
    paired = [{"example_id": "test:0", "fingerprint": "fp-0", "macro_delta": 0.0}]
    manifest = {"base_model": {"revision": "r"}, "document_identities": [{"example_id": "test:0", "fingerprint": "fp-0"}]}
    report = {
        "base_summary": summary,
        "adapter_summary": {**summary, "model_label": "adapter"},
        "paired_documents": paired,
        "paired_summary": {"documents_improved": 0, "documents_regressed": 0},
        "dataset_integrity": {"counts": {"train": 563, "validation": 63, "test": 347}},
    }
    (tmp_path / "report.json").write_text(json.dumps(report))
    (tmp_path / "evaluation_manifest.json").write_text(json.dumps(manifest))
    for name, value in (("base_predictions.json", records), ("adapter_predictions.json", adapter_records)):
        (tmp_path / name).write_text(json.dumps(value))
    for name, label, value in (("base_predictions.partial.json", "base", records), ("adapter_predictions.partial.json", "adapter", adapter_records)):
        (tmp_path / name).write_text(json.dumps({"manifest": manifest, "model_label": label, "records": value}))
    with pytest.raises(AssertionError):
        verify_artifacts(tmp_path)

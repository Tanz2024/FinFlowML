"""Verify downloaded Stage 4 evaluation artifacts without model execution."""

import argparse
import json
from pathlib import Path
from statistics import mean

from ml.data.constants import TARGET_FIELDS


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(records: list[dict], label: str) -> dict:
    return {
        "model_label": label,
        "documents": len(records),
        "json_validity_rate": mean(not r["invalid_output"] for r in records),
        "field_accuracy": {
            field: mean(r["scores"]["normalized_exact_match"][field] for r in records)
            for field in TARGET_FIELDS
        },
        "macro_field_accuracy": mean(r["scores"]["macro_field_accuracy"] for r in records),
        "all_fields_correct_rate": mean(r["scores"]["document_all_fields_correct"] for r in records),
    }


def verify_artifacts(directory: Path) -> dict:
    report = _load(directory / "report.json")
    manifest = _load(directory / "evaluation_manifest.json")
    base = _load(directory / "base_predictions.json")
    adapter = _load(directory / "adapter_predictions.json")
    base_partial = _load(directory / "base_predictions.partial.json")
    adapter_partial = _load(directory / "adapter_predictions.partial.json")
    assert isinstance(base, list) and isinstance(adapter, list)
    assert len(base) == len(adapter) == 347
    assert base_partial["records"] == base
    assert adapter_partial["records"] == adapter
    assert base_partial["manifest"] == adapter_partial["manifest"] == manifest
    base_ids = [(r["example_id"], r["fingerprint"]) for r in base]
    adapter_ids = [(r["example_id"], r["fingerprint"]) for r in adapter]
    assert base_ids == adapter_ids
    assert report["base_summary"] == {**report["base_summary"], **_summary(base, "base")}
    assert report["adapter_summary"] == {**report["adapter_summary"], **_summary(adapter, "adapter")}
    paired = report["paired_documents"]
    assert len(paired) == 347
    assert [(r["example_id"], r["fingerprint"]) for r in paired] == base_ids
    improved = sum(r["macro_delta"] > 0 for r in paired)
    regressed = sum(r["macro_delta"] < 0 for r in paired)
    assert report["paired_summary"]["documents_improved"] == improved
    assert report["paired_summary"]["documents_regressed"] == regressed
    return {
        "directory": str(directory),
        "documents": 347,
        "base": _summary(base, "base"),
        "adapter": _summary(adapter, "adapter"),
        "paired": report["paired_summary"],
        "manifest": manifest,
        "integrity": report["dataset_integrity"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_artifacts(args.directory), indent=2))


if __name__ == "__main__":
    main()

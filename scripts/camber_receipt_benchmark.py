"""Standalone Camber benchmark for the pinned Qwen + LoRA receipt path.

The manifest is local to the GPU job and is never uploaded by this script. Its
expected values are used only to compute booleans; raw OCR, model output,
receipt paths, and expected values are not written to the result files.
"""

import argparse
import csv
import json
import time
from pathlib import Path

import torch

from ml.inference.predict import (
    build_quantization_config,
    generate_prediction,
    load_inference_model,
)
from ml.ocr.extract import extract_text

DEFAULT_MODEL = "Qwen/Qwen3-4B-Instruct-2507"
DEFAULT_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
FIELDS = ("company", "receipt_date", "address", "total")


def _same(expected: object, actual: object) -> bool:
    if expected is None:
        return False
    return str(expected).strip().casefold() == str(actual or "").strip().casefold()


def _memory() -> int | None:
    return torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None


def _load_manifest(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("manifest must be a non-empty JSON list")
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not row.get("image"):
            raise ValueError(f"manifest row {index} must contain an image")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-model", default=DEFAULT_MODEL)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPU is required; benchmark not executed")
    if args.revision != DEFAULT_REVISION or args.base_model != DEFAULT_MODEL:
        raise SystemExit("refusing an unpinned base model or revision")
    if not (args.adapter / "adapter_config.json").is_file():
        raise SystemExit(f"missing adapter_config.json: {args.adapter}")
    manifest = _load_manifest(args.manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    loaded = load_inference_model(args.base_model, str(args.adapter), revision=args.revision,
                                  device_map="auto", quantization_config=build_quantization_config())
    cold_load_seconds = time.perf_counter() - started
    records: list[dict] = []
    for index, row in enumerate(manifest, 1):
        receipt_started = time.perf_counter()
        result = {"receipt_index": index, "status": "failed", "json_valid": False,
                  "parsing_error": None, "ocr_seconds": None, "inference_seconds": None,
                  "total_seconds": None, "all_fields_correct": False}
        try:
            ocr_started = time.perf_counter()
            ocr_text = extract_text(row["image"])
            ocr_seconds = time.perf_counter() - ocr_started
            inference_started = time.perf_counter()
            _, prediction, parsing_error = generate_prediction(
                loaded, ocr_text, max_new_tokens=args.max_new_tokens)
            inference_seconds = time.perf_counter() - inference_started
            result.update(status="passed" if prediction is not None and parsing_error is None else "failed",
                          json_valid=isinstance(prediction, dict), parsing_error=parsing_error,
                          ocr_seconds=round(ocr_seconds, 4), inference_seconds=round(inference_seconds, 4))
            for field in FIELDS:
                result[f"{field}_correct"] = _same(row.get("expected", {}).get(field), prediction.get(field) if prediction else None)
            result["all_fields_correct"] = all(result[f"{field}_correct"] for field in FIELDS)
        except Exception as exc:  # sanitized error type only
            result["error_type"] = type(exc).__name__
        result["total_seconds"] = round(time.perf_counter() - receipt_started, 4)
        records.append(result)
    summary = {
        "model_id": args.base_model, "model_revision": args.revision,
        "documents": len(records), "cold_load_seconds": round(cold_load_seconds, 4),
        "cuda": True, "peak_vram_bytes": _memory(),
        "json_valid": sum(item["json_valid"] for item in records),
        "parsing_errors": sum(item["parsing_error"] is not None for item in records),
        "all_fields_correct": sum(item["all_fields_correct"] for item in records),
        "field_correct": {field: sum(item.get(f"{field}_correct", False) for item in records) for field in FIELDS},
        "records": records,
    }
    (args.output_dir / "results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (args.output_dir / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
    print(json.dumps({key: value for key, value in summary.items() if key != "records"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

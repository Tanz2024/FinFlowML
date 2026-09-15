import argparse
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

from ml.data.constants import DATASET_ID, DEFAULT_SEED, TARGET_FIELDS
from ml.data.sroie import load_sroie_dataset, process_split
from ml.evaluation.metrics import metrics
from ml.extraction.baseline import MODEL_ID, BaselineModel
from ml.extraction.parser import parse_prediction
from ml.extraction.prompt import build_prompt


def runtime_metadata(model: BaselineModel, max_new_tokens: int) -> dict[str, object]:
    import torch
    import transformers

    return {
        "model_id": MODEL_ID,
        "model_revision": model.revision,
        "transformers_version": transformers.__version__,
        "pytorch_version": torch.__version__,
        "device": model.device,
        "runtime": platform.platform(),
        "dtype": model.dtype,
        "generation": {"do_sample": False, "max_new_tokens": max_new_tokens},
    }


def run_benchmark(limit: int | None = None, output_dir: Path = Path("results/baseline")) -> dict[str, object]:
    dataset = load_sroie_dataset(DATASET_ID)
    examples = process_split(dataset["test"], "test")[:limit]
    model = BaselineModel.load()
    records = []
    for example in examples:
        row = dataset["test"].remove_columns(["image"])[example.index]
        prompt = build_prompt(" ".join(row["words"]))
        raw_response, duration = model.generate(prompt)
        prediction, error = parse_prediction(raw_response)
        scoring_prediction = prediction or {field: None for field in TARGET_FIELDS}
        score = metrics(example.raw_targets, scoring_prediction)
        records.append({"example_id": example.image_reference, "fingerprint": example.fingerprint, "ground_truth": example.raw_targets, "prediction": prediction, "raw_model_output": raw_response, "invalid_output": error is not None, "parse_error": error, "incorrect_fields": [field for field in TARGET_FIELDS if not score["normalized_exact_match"][field]], "inference_seconds": duration})
    valid = [record for record in records if not record["invalid_output"]]
    totals = {field: sum(not record["invalid_output"] and metrics(record["ground_truth"], record["prediction"])["normalized_exact_match"][field] for record in records) / len(records) if records else 0.0 for field in TARGET_FIELDS}
    normalized_values = [metrics(record["ground_truth"], record["prediction"] or {})["normalized_exact_match"] for record in records]
    summary = {"total_evaluated_documents": len(records), "invalid_outputs": sum(record["invalid_output"] for record in records), "missing_predictions": sum(record["prediction"] is None for record in records), "inference_time_seconds": sum(record["inference_seconds"] for record in records), "normalized_exact_match_per_field": totals, "macro_field_accuracy": sum(sum(values.values()) / len(TARGET_FIELDS) for values in normalized_values) / len(normalized_values) if normalized_values else 0.0, "document_all_fields_correct_rate": sum(all(values.values()) for values in normalized_values) / len(normalized_values) if normalized_values else 0.0, "valid_structured_output_rate": len(valid) / len(records) if records else 0.0}
    report = {"created_at": datetime.now(UTC).isoformat(), "dataset_id": DATASET_ID, "official_test_split": True, "limit": limit, "seed": DEFAULT_SEED, "runtime": runtime_metadata(model, 192), "summary": summary, "records": records}
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = str(limit) if limit is not None else "full"
    (output_dir / f"benchmark_{suffix}.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    report = run_benchmark(args.limit)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()

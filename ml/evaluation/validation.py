from collections.abc import Iterable

from ml.evaluation.metrics import metrics
from ml.extraction.parser import parse_prediction
from ml.training.dataset import TrainingExample


def validation_metrics(records: Iterable[dict]) -> dict[str, object]:
    records = list(records)
    valid = [record for record in records if not record["invalid_output"]]
    field_values = {field: sum(record["scores"][field] for record in valid) / len(records) if records else 0.0 for field in ("company", "date", "address", "total")}
    return {"normalized_exact_match_per_field": field_values, "normalized_macro_field_accuracy": sum(field_values.values()) / 4, "all_fields_correct_rate": sum(record["all_fields_correct"] for record in valid) / len(records) if records else 0.0, "valid_structured_output_rate": len(valid) / len(records) if records else 0.0}


def evaluate_validation_predictions(examples: Iterable[TrainingExample], raw_outputs: Iterable[str]) -> dict[str, object]:
    records = []
    for example, raw_output in zip(examples, raw_outputs, strict=True):
        prediction, error = parse_prediction(raw_output)
        scored = prediction or {}
        score = metrics(example.raw_targets, scored)
        records.append({"example_id": example.example_id, "raw_model_output": raw_output, "prediction": prediction, "invalid_output": error is not None, "parse_error": error, "scores": score["normalized_exact_match"], "all_fields_correct": score["document_all_fields_correct"]})
    return validation_metrics(records)

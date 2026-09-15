from collections.abc import Mapping

from ml.data.constants import TARGET_FIELDS
from ml.data.normalize import normalize_target


def _equal(expected: str | None, predicted: str | None) -> bool:
    return expected is not None and predicted is not None and expected == predicted


def field_exact_match(expected: Mapping[str, str | None], predicted: Mapping[str, str | None], field: str) -> bool:
    return _equal(expected.get(field), predicted.get(field))


def field_normalized_exact_match(expected: Mapping[str, str | None], predicted: Mapping[str, str | None], field: str) -> bool:
    return _equal(normalize_target(field, expected.get(field)), normalize_target(field, predicted.get(field)))


def metrics(expected: Mapping[str, str | None], predicted: Mapping[str, str | None]) -> dict[str, object]:
    raw = {field: field_exact_match(expected, predicted, field) for field in TARGET_FIELDS}
    normalized = {field: field_normalized_exact_match(expected, predicted, field) for field in TARGET_FIELDS}
    return {
        "raw_exact_match": raw,
        "normalized_exact_match": normalized,
        "macro_field_accuracy": sum(normalized.values()) / len(TARGET_FIELDS),
        "document_all_fields_correct": all(normalized.values()),
        "valid_structured_output": all(field in predicted and isinstance(predicted[field], (str, type(None))) for field in TARGET_FIELDS),
    }

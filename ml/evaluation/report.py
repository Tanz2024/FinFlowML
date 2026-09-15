from collections import Counter
from collections.abc import Iterable, Mapping

from ml.data.constants import TARGET_FIELDS
from ml.data.validate import duplicate_fingerprints
from ml.extraction.schema import ExtractionExample


def dataset_statistics(splits: Mapping[str, Iterable[ExtractionExample]]) -> dict[str, object]:
    materialized = {name: list(examples) for name, examples in splits.items()}
    fingerprints = {name: [item.fingerprint for item in examples] for name, examples in materialized.items()}
    target_counts = {field: sum(item.raw_targets[field] is not None for item in materialized.get("train", [])) for field in TARGET_FIELDS}
    issue_counts = Counter(issue for examples in materialized.values() for item in examples for issue in item.validation_issues)
    return {
        "split_counts": {name: len(examples) for name, examples in materialized.items()},
        "target_counts_train": target_counts,
        "malformed_examples": sum(item.malformed for examples in materialized.values() for item in examples),
        "validation_issue_counts": dict(issue_counts),
        "cross_split_duplicate_fingerprints": duplicate_fingerprints(fingerprints),
    }

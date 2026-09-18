import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from typing import Any

from datasets import Dataset, DatasetDict, load_dataset
from huggingface_hub import hf_hub_download, list_repo_files

from ml.data.constants import DATASET_ID, LABEL_TO_FIELD
from ml.data.normalize import normalize_target
from ml.data.validate import validate_lengths
from ml.extraction.schema import ExtractionExample, empty_targets


def load_sroie_dataset(dataset_id: str = DATASET_ID, split: str | None = None) -> Dataset | DatasetDict:
    """Load SROIE as a DatasetDict, or only the requested source split."""
    if split is None:
        return load_dataset(dataset_id)
    if split != "train":
        return load_dataset(dataset_id, split=split)
    train_shards = sorted(
        filename for filename in list_repo_files(dataset_id, repo_type="dataset")
        if filename.startswith("data/train-") and filename.endswith(".parquet")
    )
    if not train_shards:
        raise FileNotFoundError(f"no train parquet shards found in dataset repository: {dataset_id}")
    train_files = [hf_hub_download(dataset_id, filename, repo_type="dataset") for filename in train_shards]
    return load_dataset("parquet", data_files=train_files, split="train")


def label_name(dataset_split: Any, tag: Any) -> str | None:
    if isinstance(tag, int):
        return dataset_split.features["ner_tags"].feature.int2str(tag)
    return str(tag) if tag is not None else None


def document_fingerprint(words: Sequence[Any]) -> str:
    payload = json.dumps([str(word).strip() for word in words], ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def process_example(dataset_split: Any, index: int, split: str) -> ExtractionExample:
    row = dataset_split.remove_columns(["image"])[index] if "image" in dataset_split.column_names else dataset_split[index]
    words = row.get("words") or []
    tags = row.get("ner_tags") or []
    bboxes = row.get("bboxes") or []
    issues = validate_lengths(words, tags, bboxes)
    raw = empty_targets()
    counts = Counter()
    for word, tag in zip(words, tags, strict=False):
        field = LABEL_TO_FIELD.get(label_name(dataset_split, tag))
        if field:
            raw[field] = f"{raw[field]} {word}".strip() if raw[field] else str(word).strip()
            counts[field] += 1
    issues.extend(f"multiple_regions:{field}" for field, count in counts.items() if count > 1)
    normalized = {field: normalize_target(field, value) for field, value in raw.items()}
    return ExtractionExample(split, index, document_fingerprint(words), raw, normalized, bool(issues and any(i.startswith("length_mismatch") for i in issues)), tuple(issues), f"{split}:{index}")


def process_split(dataset_split: Any, split: str) -> list[ExtractionExample]:
    return [process_example(dataset_split, index, split) for index in range(len(dataset_split))]

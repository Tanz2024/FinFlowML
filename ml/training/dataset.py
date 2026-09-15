import json
from dataclasses import dataclass
from statistics import median
from typing import Any

from ml.data.split import split_examples
from ml.data.sroie import load_sroie_dataset, process_split
from ml.extraction.prompt import build_prompt


@dataclass(frozen=True)
class TrainingExample:
    example_id: str
    fingerprint: str
    messages: list[dict[str, str]]
    raw_targets: dict[str, str | None]


def target_json(raw_targets: dict[str, str | None]) -> str:
    return json.dumps(raw_targets, ensure_ascii=False, separators=(",", ":"))


def format_training_example(words: list[str], raw_targets: dict[str, str | None], example_id: str, fingerprint: str) -> TrainingExample:
    return TrainingExample(example_id, fingerprint, [{"role": "user", "content": build_prompt(" ".join(words))}, {"role": "assistant", "content": target_json(raw_targets)}], raw_targets)


def load_train_validation(dataset_id: str = "mp-02/sroie", seed: int = 42) -> tuple[list[TrainingExample], list[TrainingExample]]:
    dataset = load_sroie_dataset(dataset_id)
    processed = process_split(dataset["train"], "source_train")
    train_processed, validation_processed = split_examples(processed, seed=seed)
    rows = dataset["train"].remove_columns(["image"])

    def convert(items: list[Any], split: str) -> list[TrainingExample]:
        return [format_training_example(rows[item.index]["words"], item.raw_targets, f"{split}:{item.index}", item.fingerprint) for item in items]

    return convert(train_processed, "train"), convert(validation_processed, "validation")


def assistant_only_tokens(example: TrainingExample, tokenizer: Any) -> dict[str, list[int]]:
    prompt_text = tokenizer.apply_chat_template(example.messages[:1], tokenize=False, add_generation_prompt=True)
    full_text = tokenizer.apply_chat_template(example.messages, tokenize=False, add_generation_prompt=False)
    prompt_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
    full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]
    labels = [-100] * min(len(prompt_ids), len(full_ids)) + full_ids[len(prompt_ids):]
    return {"input_ids": full_ids, "labels": labels, "attention_mask": [1] * len(full_ids)}


def verify_assistant_only_mask(example: TrainingExample, tokenizer: Any) -> None:
    encoded = assistant_only_tokens(example, tokenizer)
    prompt_text = tokenizer.apply_chat_template(example.messages[:1], tokenize=False, add_generation_prompt=True)
    prompt_length = len(tokenizer(prompt_text, add_special_tokens=False)["input_ids"])
    if encoded["labels"][:prompt_length] != [-100] * prompt_length:
        raise ValueError("assistant-only loss mask does not mask the complete prompt")
    if not any(label != -100 for label in encoded["labels"][prompt_length:]):
        raise ValueError("assistant-only loss mask contains no assistant response tokens")


def token_length_statistics(examples: list[TrainingExample], tokenizer: Any) -> dict[str, int | float]:
    lengths = []
    for example in examples:
        rendered = tokenizer.apply_chat_template(example.messages, tokenize=False, add_generation_prompt=False)
        lengths.append(len(tokenizer(rendered, add_special_tokens=False)["input_ids"]))
    ordered = sorted(lengths)

    def percentile(value: float) -> float:
        if not ordered:
            return 0
        position = (len(ordered) - 1) * value
        lower, upper = int(position), min(int(position) + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {"count": len(lengths), "median": median(lengths) if lengths else 0, "p95": percentile(0.95), "p99": percentile(0.99), "maximum": max(lengths, default=0), "exceeding_1024": sum(length > 1024 for length in lengths), "exceeding_2048": sum(length > 2048 for length in lengths)}

import pytest

from ml.training.config import TrainingConfig
from ml.training.dataset import (
    assistant_only_tokens,
    format_training_example,
    target_json,
    verify_assistant_only_mask,
)


def test_training_format_uses_raw_targets_and_assistant_response():
    targets = {"company": "ACME", "date": None, "address": "A Road", "total": "10.00"}
    example = format_training_example(["ACME", "TOTAL", "10.00"], targets, "train:1", "fp")
    assert example.messages[1]["role"] == "assistant"
    assert target_json(targets) in example.messages[1]["content"]


def test_config_validation():
    TrainingConfig().validate()
    with pytest.raises(ValueError):
        TrainingConfig(packing=True).validate()


def test_training_loader_rejects_test_split(monkeypatch):
    import ml.training.dataset as dataset_module

    accessed = []

    class TrainOnly(dict):
        def __getitem__(self, key):
            accessed.append(key)
            return super().__getitem__(key)

    class EmptyDataset:
        column_names = []
        def __len__(self): return 0
        def __getitem__(self, index): raise IndexError(index)

        def remove_columns(self, columns): return self

    monkeypatch.setattr(dataset_module, "load_sroie_dataset", lambda _: TrainOnly(train=EmptyDataset()))
    dataset_module.load_train_validation()
    assert set(accessed) == {"train"}


def test_assistant_only_loss_masks_prompt():
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            return "USER" if len(messages) == 1 else "USERASSISTANT"

        def __call__(self, text, **kwargs):
            return {"input_ids": list(range(2 if text == "USER" else 4))}

    example = format_training_example(["ACME"], {"company": "ACME", "date": None, "address": None, "total": None}, "train:1", "fp")
    tokens = assistant_only_tokens(example, Tokenizer())
    assert tokens["labels"] == [-100, -100, 2, 3]
    verify_assistant_only_mask(example, Tokenizer())


def test_smoke_example_validation_rejects_empty_assistant_labels():
    from ml.training.train import _validate_smoke_example

    with pytest.raises(ValueError, match="no assistant response"):
        _validate_smoke_example({"input_ids": [1], "attention_mask": [1], "labels": [-100]})

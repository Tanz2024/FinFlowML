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

    requested = []

    class EmptyDataset:
        column_names = []
        def __len__(self): return 0
        def __getitem__(self, index): raise IndexError(index)

        def remove_columns(self, columns): return self

    def load_train_only(dataset_id, split=None):
        requested.append((dataset_id, split))
        return EmptyDataset()

    monkeypatch.setattr(dataset_module, "load_sroie_dataset", load_train_only)
    dataset_module.load_train_validation()
    assert requested == [("mp-02/sroie", "train")]


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


def test_generation_temporarily_uses_eval_and_restores_model_state():
    import torch

    from ml.training.train import _generate

    class Inputs(dict):
        def to(self, device):
            return self

    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            return "prompt"

        def __call__(self, prompt, **kwargs):
            return Inputs(input_ids=torch.tensor([[1, 2]]))

        def decode(self, tokens, **kwargs):
            return "{}"

    class Config:
        use_cache = False

    class Model(torch.nn.Module):
        config = Config()
        device = torch.device("cpu")

        def generate(self, **kwargs):
            assert self.training is False
            assert self.config.use_cache is True
            return torch.tensor([[1, 2, 3]])

    model = Model()
    model.train()
    outputs = _generate(model, Tokenizer(), [type("Example", (), {"messages": []})()], 192)
    assert outputs == ["{}"]
    assert model.training is True
    assert model.config.use_cache is False


def test_full_training_selection_and_amp_classification():
    from ml.training.train import classify_amp_records, select_best_validation

    history = [{"epoch": 1, "normalized_macro_field_accuracy": 0.2},
               {"epoch": 2, "normalized_macro_field_accuracy": 0.4}]
    assert select_best_validation(history)["epoch"] == 2
    records = [{"tensors_with_nan": 1, "tensors_with_inf": 0},
               {"tensors_with_nan": 0, "tensors_with_inf": 0}]
    assert classify_amp_records(records) == {"initial_overflow": True, "persistent_after_recovery": False}


def test_checkpoint_discovery_ignores_epoch_adapters_and_selects_latest(tmp_path):
    from ml.training.train import discover_latest_checkpoint

    (tmp_path / "epoch_2_adapter").mkdir()
    for number in (5, 10):
        checkpoint = tmp_path / f"checkpoint-{number}"
        checkpoint.mkdir()
        for filename in ("trainer_state.json", "adapter_model.safetensors", "optimizer.pt", "scheduler.pt"):
            (checkpoint / filename).touch()
    assert discover_latest_checkpoint(tmp_path) == tmp_path / "checkpoint-10"


def test_checkpoint_discovery_rejects_incomplete_checkpoint(tmp_path):
    from ml.training.train import discover_latest_checkpoint

    checkpoint = tmp_path / "checkpoint-10"
    checkpoint.mkdir()
    (checkpoint / "trainer_state.json").touch()
    assert discover_latest_checkpoint(tmp_path) is None


def test_no_resume_ignores_valid_checkpoint(tmp_path):
    from ml.training.train import checkpoint_for_resume

    checkpoint = tmp_path / "checkpoint-10"
    checkpoint.mkdir()
    for filename in ("trainer_state.json", "adapter_model.safetensors", "optimizer.pt", "scheduler.pt"):
        (checkpoint / filename).touch()
    assert checkpoint_for_resume(tmp_path, no_resume=True) is None
    assert checkpoint_for_resume(tmp_path, no_resume=False) == checkpoint


def test_validation_history_survives_interruption_and_resume(tmp_path):
    from ml.training.train import (
        load_validation_history,
        persist_validation_history,
        upsert_validation_history,
    )

    history_path = tmp_path / "validation_history.json"

    def epoch_entry(epoch):
        return {"epoch": epoch, "normalized_macro_field_accuracy": epoch / 10}

    history = []
    upsert_validation_history(history, epoch_entry(1))
    persist_validation_history(history_path, history)

    restored = load_validation_history(history_path, resume=True)
    for epoch in (1, 2, 3):
        upsert_validation_history(restored, epoch_entry(epoch))
        persist_validation_history(history_path, restored)

    assert [entry["epoch"] for entry in load_validation_history(history_path, resume=True)] == [1, 2, 3]
    assert len(load_validation_history(history_path, resume=True)) == 3
    assert load_validation_history(history_path, resume=False) == []

import sys
import types

import pytest

from ml.modeling.loader import ModelLoadingError, load_finflow_model, validate_adapter_path


def _fake_ml_modules(monkeypatch):
    calls = {}

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls["tokenizer"] = (path, kwargs)
            return "tokenizer"

    class AutoModel:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls["model"] = (path, kwargs)
            return "base-model"

    class PeftModel:
        @staticmethod
        def from_pretrained(model, path):
            calls["adapter"] = (model, path)
            return "adapted-model"

    transformers = types.ModuleType("transformers")
    transformers.AutoTokenizer = AutoTokenizer
    transformers.AutoModelForCausalLM = AutoModel
    peft = types.ModuleType("peft")
    peft.PeftModel = PeftModel
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "peft", peft)
    return calls


def test_loads_tokenizer_and_base_from_base_then_applies_adapter(tmp_path, monkeypatch):
    adapter = tmp_path / "best_adapter"
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}")
    (adapter / "adapter_model.safetensors").write_bytes(b"weights")
    calls = _fake_ml_modules(monkeypatch)

    loaded = load_finflow_model("Qwen/Qwen3-4B-Instruct-2507", adapter)

    assert loaded.model == "adapted-model"
    assert calls["tokenizer"][0] == "Qwen/Qwen3-4B-Instruct-2507"
    assert calls["model"][0] == "Qwen/Qwen3-4B-Instruct-2507"
    assert calls["adapter"] == ("base-model", str(adapter))


def test_rejects_adapter_directory_as_base_before_tokenizer_load(tmp_path, monkeypatch):
    adapter = tmp_path / "epoch_1_adapter"
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}")
    (adapter / "adapter_model.safetensors").write_bytes(b"weights")
    calls = _fake_ml_modules(monkeypatch)

    with pytest.raises(ModelLoadingError, match="[Bb]ase model points to a LoRA adapter"):
        load_finflow_model(adapter)
    assert "tokenizer" not in calls


def test_validates_adapter_artifacts(tmp_path):
    with pytest.raises(ModelLoadingError, match="does not exist"):
        validate_adapter_path(tmp_path / "missing")

    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    with pytest.raises(ModelLoadingError, match="Missing adapter_config.json"):
        validate_adapter_path(incomplete)

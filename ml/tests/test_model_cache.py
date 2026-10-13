import ml.inference.predict as inference
from ml.modeling.loader import LoadedModel


def test_inference_model_cache_reuses_loaded_adapter(monkeypatch):
    calls = []
    monkeypatch.setattr(inference, "_MODEL_CACHE", {})
    monkeypatch.setattr(inference, "load_finflow_model", lambda *args, **kwargs: calls.append((args, kwargs)) or LoadedModel(model=object(), tokenizer=object()))
    inference.load_inference_model("base", "adapter", revision="rev")
    inference.load_inference_model("base", "adapter", revision="rev")
    inference.load_inference_model("base", "adapter", revision="other")
    assert len(calls) == 2

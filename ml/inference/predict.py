"""Inference loading entry point.

Callers should use :func:`load_inference_model` so adapters are always applied
to a complete base model.
"""

from typing import Any

from ml.modeling.loader import LoadedModel, load_finflow_model


def load_inference_model(
    base_model: str,
    adapter_path: str | None = None,
    **kwargs: Any,
) -> LoadedModel:
    """Load the base tokenizer/model, then apply the optional LoRA adapter."""

    return load_finflow_model(base_model, adapter_path, **kwargs)


if __name__ == "__main__":
    print("FinFlowML inference loader is ready; call load_inference_model() to load a model.")

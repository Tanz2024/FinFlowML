"""Load a FinFlowML base model and, optionally, a LoRA adapter.

PEFT adapter directories are deliberately never used as a source for the
tokenizer or base model.  They contain only adapter weights and metadata.
"""

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any


class ModelLoadingError(ValueError):
    """Raised when model and adapter paths do not describe a valid layout."""


@dataclass
class LoadedModel:
    """The tokenizer and model produced by :func:`load_finflow_model`."""

    model: Any
    tokenizer: Any


def _is_adapter_directory(path: str | PathLike[str]) -> bool:
    directory = Path(path)
    return (directory / "adapter_config.json").is_file() or (
        (directory / "adapter_model.safetensors").is_file()
        or (directory / "adapter_model.bin").is_file()
    )


def validate_adapter_path(adapter_path: str | PathLike[str]) -> Path:
    """Validate and return an adapter directory containing PEFT artifacts."""

    path = Path(adapter_path)
    if not path.is_dir():
        raise ModelLoadingError(f"LoRA adapter directory does not exist: {path}")
    if not (path / "adapter_config.json").is_file():
        raise ModelLoadingError(f"Missing adapter_config.json in LoRA adapter: {path}")
    if not any((path / name).is_file() for name in ("adapter_model.safetensors", "adapter_model.bin")):
        raise ModelLoadingError(f"Missing adapter weights in LoRA adapter: {path}")
    return path


def validate_base_model_path(base_model: str | PathLike[str]) -> None:
    """Reject a local PEFT adapter accidentally supplied as the base model."""

    if _is_adapter_directory(base_model):
        raise ModelLoadingError(
            f"Base model points to a LoRA adapter directory ({base_model}). "
            "Pass the complete Hugging Face base model and supply the adapter via adapter_path."
        )


def load_finflow_model(
    base_model: str | PathLike[str],
    adapter_path: str | PathLike[str] | None = None,
    *,
    quantization_config: Any = None,
    device_map: Any = None,
    revision: str | None = None,
    **model_kwargs: Any,
) -> LoadedModel:
    """Load tokenizer/config/architecture from ``base_model`` and apply PEFT.

    Imports are intentionally lazy so validation and unit tests do not require
    CUDA, bitsandbytes, or model downloads.
    """

    validate_base_model_path(base_model)
    adapter = validate_adapter_path(adapter_path) if adapter_path is not None else None

    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer_kwargs = {"revision": revision} if revision is not None else {}
    tokenizer = AutoTokenizer.from_pretrained(str(base_model), **tokenizer_kwargs)
    load_kwargs = dict(model_kwargs)
    if quantization_config is not None:
        load_kwargs["quantization_config"] = quantization_config
    if device_map is not None:
        load_kwargs["device_map"] = device_map
    if revision is not None:
        load_kwargs["revision"] = revision
    model = AutoModelForCausalLM.from_pretrained(str(base_model), **load_kwargs)

    if adapter is not None:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, str(adapter))
    return LoadedModel(model=model, tokenizer=tokenizer)

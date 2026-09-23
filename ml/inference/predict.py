"""Inference loading and smoke-test entry point."""

import os
from typing import Any

import torch
from transformers import BitsAndBytesConfig

from ml.extraction.parser import parse_prediction
from ml.extraction.prompt import build_prompt
from ml.modeling.loader import LoadedModel, load_finflow_model


def load_inference_model(
    base_model: str,
    adapter_path: str | None = None,
    **kwargs: Any,
) -> LoadedModel:
    """Load the base tokenizer/model, then apply the optional LoRA adapter."""

    return load_finflow_model(base_model, adapter_path, **kwargs)


def predict(
    ocr_text: str,
    base_model: str,
    adapter_path: str | None = None,
    *,
    max_new_tokens: int = 256,
) -> tuple[str, dict[str, str | None] | None, str | None]:
    """Generate and parse a structured prediction from receipt OCR text."""

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    loaded = load_inference_model(
        base_model,
        adapter_path,
        quantization_config=quantization_config,
        device_map="auto",
    )
    prompt = build_prompt(ocr_text)
    messages = [{"role": "user", "content": prompt}]
    rendered_prompt = loaded.tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=False
    )
    inputs = loaded.tokenizer(rendered_prompt, return_tensors="pt")
    device = getattr(loaded.model, "device", None)
    if device is not None and hasattr(inputs, "to"):
        inputs = inputs.to(device)
    output = loaded.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    input_ids = inputs["input_ids"]
    generated_tokens = output[0][input_ids.shape[-1] :]
    raw_output = loaded.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()
    prediction, parsing_error = parse_prediction(raw_output)
    return raw_output, prediction, parsing_error


if __name__ == "__main__":
    base_model = "Qwen/Qwen3-4B-Instruct-2507"
    training_dir = os.environ.get(
        "FINFLOW_TRAINING_DIR", "/content/drive/MyDrive/FinFlowML-stage4-final-v2"
    )
    adapter_path = os.environ.get("ADAPTER_PATH", os.path.join(training_dir, "best_adapter"))
    sample_ocr = """SUPERMARKET RECEIPT
Date: 2025-01-15
Subtotal: 10.00
Tax: 0.80
TOTAL: 10.80
Thank you"""

    raw_output, prediction, parsing_error = predict(sample_ocr, base_model, adapter_path)
    print(f"Raw generated output:\n{raw_output}")
    print(f"Parsed prediction:\n{prediction}")
    print(f"Parsing error: {parsing_error}")

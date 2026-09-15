import argparse
import json
import time
from pathlib import Path

from ml.training.config import TrainingConfig
from ml.training.dataset import load_train_validation, token_length_statistics


def hardware_config():
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("Stage 4 QLoRA requires a CUDA NVIDIA GPU; MPS/CPU is not supported")
    major, _ = torch.cuda.get_device_capability()
    bf16 = torch.cuda.is_bf16_supported() and major >= 8
    return {"compute_dtype": torch.bfloat16 if bf16 else torch.float16, "bf16": bf16, "fp16": not bf16, "device": torch.cuda.get_device_name(0), "cuda_version": torch.version.cuda}


def load_quantized_model(config: TrainingConfig):
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    hardware = hardware_config()
    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=hardware["compute_dtype"])
    tokenizer = AutoTokenizer.from_pretrained(config.model_id, revision=config.model_revision)
    model = AutoModelForCausalLM.from_pretrained(config.model_id, revision=config.model_revision, quantization_config=quantization, device_map={"": 0})
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(r=config.lora_r, lora_alpha=config.lora_alpha, lora_dropout=config.lora_dropout, target_modules=list(config.target_modules), task_type="CAUSAL_LM"))
    return model, tokenizer, hardware, quantization


def smoke_test(config: TrainingConfig) -> dict[str, object]:
    config.validate()
    started = time.perf_counter()
    train, validation = load_train_validation(config.dataset_id, config.seed)
    model, tokenizer, hardware, quantization = load_quantized_model(config)
    stats = token_length_statistics(train + validation, tokenizer)
    if stats["exceeding_2048"]:
        raise ValueError("Training examples exceed max_seq_length; refusing silent truncation")
    model.print_trainable_parameters()
    metadata = {"model_id": config.model_id, "revision": config.model_revision, "dataset_id": config.dataset_id, "seed": config.seed, "hardware": {key: str(value) for key, value in hardware.items()}, "quantization": {"load_in_4bit": True, "bnb_4bit_quant_type": "nf4", "bnb_4bit_use_double_quant": True, "bnb_4bit_compute_dtype": str(hardware["compute_dtype"])}, "token_length_statistics": stats, "train_examples": len(train), "validation_examples": len(validation), "duration_seconds": time.perf_counter() - started}
    output = Path(config.output_dir) / "smoke_metadata.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if not args.smoke:
        raise SystemExit("Full training is intentionally not enabled in the Stage 4 infrastructure smoke phase")
    print(json.dumps(smoke_test(TrainingConfig()), indent=2))


if __name__ == "__main__":
    main()

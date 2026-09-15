import argparse
import gc
import json
import math
import time
from pathlib import Path

from ml.evaluation.validation import evaluate_validation_predictions
from ml.extraction.parser import parse_prediction
from ml.training.config import TrainingConfig
from ml.training.dataset import (
    assistant_only_tokens,
    load_train_validation,
    token_length_statistics,
    verify_assistant_only_mask,
)


def hardware_config():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("Stage 4 QLoRA requires a CUDA NVIDIA GPU; MPS/CPU is not supported")
    major, _ = torch.cuda.get_device_capability()
    bf16 = torch.cuda.is_bf16_supported() and major >= 8
    return {"compute_dtype": torch.bfloat16 if bf16 else torch.float16, "bf16": bf16,
            "fp16": not bf16, "device": torch.cuda.get_device_name(0),
            "cuda_version": torch.version.cuda, "device_index": 0}


def load_quantized_model(config: TrainingConfig):
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    hardware = hardware_config()
    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=hardware["compute_dtype"])
    tokenizer = AutoTokenizer.from_pretrained(config.model_id, revision=config.model_revision)
    model = AutoModelForCausalLM.from_pretrained(config.model_id, revision=config.model_revision,
        quantization_config=quantization, device_map={"": 0})
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(r=config.lora_r, lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout, target_modules=list(config.target_modules), task_type="CAUSAL_LM"))
    return model, tokenizer, hardware, quantization


class _Collator:
    def __init__(self, tokenizer, max_length):
        self.tokenizer, self.max_length = tokenizer, max_length

    def __call__(self, examples):
        import torch
        encoded = [dict(item) for item in examples]
        max_len = min(self.max_length, max(len(item["input_ids"]) for item in encoded))
        batch = {}
        for key in ("input_ids", "labels", "attention_mask"):
            pad = 0 if key == "attention_mask" else -100
            batch[key] = torch.tensor([item[key][:max_len] + [pad] * (max_len - len(item[key])) for item in encoded])
        return batch


def _validate_smoke_example(encoded):
    import math
    for name in ("input_ids", "attention_mask", "labels"):
        values = encoded[name]
        if not values or any(not isinstance(value, int) for value in values):
            raise ValueError(f"smoke {name} contains malformed values")
        if any(not math.isfinite(value) for value in values):
            raise ValueError(f"smoke {name} contains non-finite values")
    if not any(label != -100 for label in encoded["labels"]):
        raise ValueError("first smoke example has no assistant response labels")


class _GradientDiagnostics:
    def __init__(self, TrainerCallback):
        class Callback(TrainerCallback):
            def __init__(self):
                self.records = []
                self.step_events = []
                self.weight_before = None

            def _weights(self, model):
                return [parameter.detach().flatten()[:4].float().cpu().tolist()
                        for parameter in model.parameters() if parameter.requires_grad][:8]

            def on_pre_optimizer_step(self, args, state, control, model=None, **kwargs):
                import torch
                tensors = [parameter.grad.detach() for parameter in model.parameters()
                           if parameter.requires_grad and parameter.grad is not None]
                finite = [value for tensor in tensors for value in tensor.detach().float().abs().flatten().tolist()
                          if torch.isfinite(torch.tensor(value))]
                self.records.append({"global_step": state.global_step,
                    "tensors_with_gradients": len(tensors),
                    "tensors_with_nan": sum(torch.isnan(tensor).any().item() for tensor in tensors),
                    "tensors_with_inf": sum(torch.isinf(tensor).any().item() for tensor in tensors),
                    "maximum_absolute_finite_gradient": max(finite, default=None)})
                if self.weight_before is None:
                    self.weight_before = self._weights(model)

            def on_optimizer_step(self, args, state, control, **kwargs):
                self.step_events.append({"global_step": state.global_step, "optimizer_step_called": True})

            def on_step_end(self, args, state, control, model=None, **kwargs):
                if self.step_events:
                    self.step_events[-1]["global_step_after"] = state.global_step
                    self.step_events[-1]["weight_sample_changed"] = self.weight_before != self._weights(model) if self.weight_before else False

        self.callback = Callback()


def _generate(model, tokenizer, examples, max_length):
    outputs = []
    for example in examples:
        prompt = tokenizer.apply_chat_template(example.messages[:1], tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        generated = model.generate(**inputs, max_new_tokens=max_length, do_sample=False)
        outputs.append(tokenizer.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip())
    return outputs


def smoke_test(config: TrainingConfig) -> dict[str, object]:
    config.validate()
    started = time.perf_counter()
    train, validation = load_train_validation(config.dataset_id, config.seed)
    smoke_train, smoke_validation = train[:config.smoke_train_examples], validation[:5]
    model, tokenizer, hardware, _ = load_quantized_model(config)
    stats = token_length_statistics(train + validation, tokenizer)
    if stats["exceeding_2048"]:
        raise ValueError("Training examples exceed max_seq_length; refusing silent truncation")
    verify_assistant_only_mask(smoke_train[0], tokenizer)
    from datasets import Dataset
    from transformers import Trainer, TrainingArguments
    encoded_train = Dataset.from_list([assistant_only_tokens(example, tokenizer) for example in smoke_train])
    _validate_smoke_example(encoded_train[0])
    from transformers import TrainerCallback
    diagnostics = _GradientDiagnostics(TrainerCallback=TrainerCallback)
    args = TrainingArguments(output_dir=str(Path(config.output_dir) / "smoke_work"), max_steps=config.smoke_steps,
        per_device_train_batch_size=1, gradient_accumulation_steps=1, learning_rate=config.learning_rate,
        logging_steps=1, save_strategy="no", report_to=[], fp16=hardware["fp16"], bf16=hardware["bf16"],
        optim=config.optimizer, gradient_checkpointing=config.gradient_checkpointing)
    trainer = Trainer(model=model, args=args, train_dataset=encoded_train, callbacks=[diagnostics.callback],
                      data_collator=_Collator(tokenizer, config.max_seq_length))
    result = trainer.train()
    losses = [entry["loss"] for entry in trainer.state.log_history if "loss" in entry]
    grad_norms = [entry["grad_norm"] for entry in trainer.state.log_history if "grad_norm" in entry]
    intended_steps = min(config.smoke_steps, len(encoded_train))
    skipped_steps = max(0, intended_steps - len(diagnostics.callback.step_events))
    trainer_global_step = trainer.state.global_step
    persistent_nonfinite = any(record["tensors_with_nan"] or record["tensors_with_inf"] for record in diagnostics.callback.records[-2:])
    if persistent_nonfinite or skipped_steps:
        raise RuntimeError("smoke diagnostics found persistent non-finite gradients or a skipped optimizer update")
    scaler = getattr(getattr(trainer, "accelerator", None), "scaler", None)
    adapter_dir = Path(config.output_dir).parent / "training" / "smoke_adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    del trainer, model
    gc.collect()
    import torch
    torch.cuda.empty_cache()
    reloaded, reload_tokenizer, _, _ = load_quantized_model(config)
    reloaded.load_adapter(str(adapter_dir), adapter_name="default")
    raw_outputs = _generate(reloaded, reload_tokenizer, smoke_validation, config.max_seq_length)
    validation_result = evaluate_validation_predictions(smoke_validation, raw_outputs)
    smoke_metrics = {
        "valid_output_rate": validation_result["valid_structured_output_rate"],
        "company_accuracy": validation_result["normalized_exact_match_per_field"]["company"],
        "date_accuracy": validation_result["normalized_exact_match_per_field"]["date"],
        "address_accuracy": validation_result["normalized_exact_match_per_field"]["address"],
        "total_accuracy": validation_result["normalized_exact_match_per_field"]["total"],
        "macro_accuracy": validation_result["normalized_macro_field_accuracy"],
    }
    for example, raw in zip(smoke_validation, raw_outputs, strict=True):
        prediction, _ = parse_prediction(raw)
        incorrect = [field for field in example.raw_targets if not prediction or prediction.get(field) != example.raw_targets[field]]
        print(json.dumps({"example_id": example.example_id, "ground_truth": example.raw_targets,
                          "raw_generated_output": raw, "parsed_prediction": prediction,
                          "incorrect_fields": incorrect}, ensure_ascii=False))
    del reloaded
    gc.collect()
    torch.cuda.empty_cache()
    metadata = {"starting_loss": losses[0] if losses else result.training_loss, "training_losses": losses,
        "final_smoke_loss": losses[-1] if losses else result.training_loss, "trainable_parameters": trainable,
        "gpu": {key: str(value) for key, value in hardware.items()}, "train_examples": len(smoke_train),
        "validation_examples": len(smoke_validation), "official_test_split_loaded": False,
        "validation_metrics": smoke_metrics, "validation_metrics_detail": validation_result,
        "adapter_dir": str(adapter_dir),
        "quantization": {"load_in_4bit": True, "nf4": True, "double_quantization": True},
        "gradient_diagnostics": {"all_logged_grad_norms_finite": all(math.isfinite(float(value)) for value in grad_norms),
            "logged_grad_norms": grad_norms, "intended_optimizer_steps": intended_steps,
            "optimizer_steps_applied": len(diagnostics.callback.step_events),
            "trainer_global_step": trainer_global_step,
            "optimizer_events": diagnostics.callback.step_events,
            "pre_optimizer_gradients": diagnostics.callback.records,
            "amp_grad_scaler": {"available": scaler is not None, "state": repr(scaler.state_dict()) if scaler else None},
            "persistent_nonfinite_gradients": persistent_nonfinite, "skipped_optimizer_steps": skipped_steps},
        "duration_seconds": time.perf_counter() - started}
    output = Path(config.output_dir) / "smoke_metadata.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if not args.smoke:
        raise SystemExit("Full training is intentionally not enabled")
    print(json.dumps(smoke_test(TrainingConfig()), indent=2))


if __name__ == "__main__":
    main()

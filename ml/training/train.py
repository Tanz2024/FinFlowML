import argparse
import gc
import json
import math
import os
import tempfile
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

            def _weight_samples(self, model):
                """Return scalar GPU-side samples sufficient to detect updates."""
                return [parameter.detach().float().mean().item()
                        for parameter in model.parameters() if parameter.requires_grad][:8]

            def on_pre_optimizer_step(self, args, state, control, model=None, **kwargs):
                import torch
                tensors = [parameter.grad.detach() for parameter in model.parameters()
                           if parameter.requires_grad and parameter.grad is not None]
                nan_count = sum(torch.isnan(tensor).any().item() for tensor in tensors)
                inf_count = sum(torch.isinf(tensor).any().item() for tensor in tensors)
                detailed = len(self.records) < 8 or nan_count > 0 or inf_count > 0
                maximum = None
                if detailed:
                    finite_maxima = []
                    for tensor in tensors:
                        values = tensor.detach().float()
                        finite_maxima.append(torch.where(torch.isfinite(values), values.abs(), 0).amax())
                    if finite_maxima:
                        maximum = torch.stack(finite_maxima).amax().item()
                self.records.append({"global_step": state.global_step,
                    "tensors_with_gradients": len(tensors), "tensors_with_nan": nan_count,
                    "tensors_with_inf": inf_count, "maximum_absolute_finite_gradient": maximum,
                    "detailed": detailed})
                if self.weight_before is None:
                    self.weight_before = self._weight_samples(model)

            def on_optimizer_step(self, args, state, control, **kwargs):
                self.step_events.append({"global_step": state.global_step, "optimizer_step_called": True})

            def on_step_end(self, args, state, control, model=None, **kwargs):
                if self.step_events:
                    self.step_events[-1]["global_step_after"] = state.global_step
                    current = self._weight_samples(model)
                    self.step_events[-1]["weight_sample_changed"] = self.weight_before != current if self.weight_before else False

        self.callback = Callback()


def _generate(model, tokenizer, examples, max_length):
    outputs = []
    was_training = model.training
    previous_use_cache = model.config.use_cache
    import torch

    model.eval()
    model.config.use_cache = True
    try:
        with torch.inference_mode():
            for index, example in enumerate(examples, start=1):
                prompt = tokenizer.apply_chat_template(example.messages[:1], tokenize=False, add_generation_prompt=True)
                inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
                generated = model.generate(**inputs, max_new_tokens=max_length, do_sample=False)
                outputs.append(tokenizer.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip())
                if index == 1 or index % 5 == 0 or index == len(examples):
                    print(f"Validation generation: {index}/{len(examples)}")
    finally:
        model.config.use_cache = previous_use_cache
        if was_training:
            model.train()
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
    raw_outputs = _generate(reloaded, reload_tokenizer, smoke_validation, 192)
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


def _metric_summary(result):
    fields = result["normalized_exact_match_per_field"]
    return {"valid_structured_output_rate": result["valid_structured_output_rate"],
            "company_accuracy": fields["company"], "date_accuracy": fields["date"],
            "address_accuracy": fields["address"], "total_accuracy": fields["total"],
            "normalized_macro_field_accuracy": result["normalized_macro_field_accuracy"],
            "all_fields_correct_rate": result["all_fields_correct_rate"]}


def select_best_validation(history):
    return max(history, key=lambda entry: entry["normalized_macro_field_accuracy"])


def classify_amp_records(records):
    later = records[1:]
    return {"initial_overflow": bool(records and (records[0]["tensors_with_nan"] or records[0]["tensors_with_inf"])),
            "persistent_after_recovery": sum(record["tensors_with_nan"] or record["tensors_with_inf"] for record in later) >= 2}


def stage4_output_root(config: TrainingConfig) -> Path:
    """Return the persistent Stage 4 root, allowing Colab/Drive override."""
    configured = os.environ.get("FINFLOW_TRAINING_DIR")
    return Path(configured) if configured else Path(config.output_dir).parent / "training"


def _checkpoint_has_any(path: Path, names: tuple[str, ...]) -> bool:
    return any((path / name).is_file() for name in names)


def discover_latest_checkpoint(work_dir: Path) -> Path | None:
    """Find the newest complete Trainer checkpoint, excluding epoch adapter exports."""
    candidates = []
    for path in work_dir.glob("checkpoint-*"):
        if not path.is_dir() or not path.name.removeprefix("checkpoint-").isdigit():
            continue
        # These are the artifacts Trainer needs for continuation. In particular,
        # adapter exports elsewhere in the training root are intentionally ignored.
        complete = (
            (path / "trainer_state.json").is_file()
            and _checkpoint_has_any(path, ("adapter_model.safetensors", "adapter_model.bin"))
            and _checkpoint_has_any(path, ("optimizer.pt", "optimizer.bin"))
            and (path / "scheduler.pt").is_file()
        )
        if complete:
            candidates.append(path)
    return max(candidates, key=lambda path: int(path.name.removeprefix("checkpoint-")), default=None)


def checkpoint_for_resume(work_dir: Path, no_resume: bool) -> Path | None:
    return None if no_resume else discover_latest_checkpoint(work_dir)


def load_validation_history(path: Path, resume: bool) -> list[dict[str, object]]:
    if not resume or not path.is_file():
        return []
    history = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(history, list):
        raise ValueError(f"validation history must be a list: {path}")
    return sorted(history, key=lambda entry: int(entry["epoch"]))


def persist_validation_history(path: Path, history: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(history, key=lambda entry: int(entry["epoch"]))
    with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.",
                                    suffix=".tmp", encoding="utf-8", delete=False) as temporary:
        json.dump(ordered, temporary, indent=2)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def upsert_validation_history(history: list[dict[str, object]], entry: dict[str, object]) -> None:
    epoch = int(entry["epoch"])
    history[:] = [existing for existing in history if int(existing["epoch"]) != epoch]
    history.append(entry)
    history.sort(key=lambda existing: int(existing["epoch"]))


def full_train(config: TrainingConfig) -> dict[str, object]:
    config.validate()
    started = time.perf_counter()
    train, validation = load_train_validation(config.dataset_id, config.seed)
    if len(train) != 563 or len(validation) != 63:
        raise ValueError(f"unexpected Stage 4 split sizes: train={len(train)}, validation={len(validation)}")
    model, tokenizer, hardware, _ = load_quantized_model(config)
    model.config.use_cache = False
    stats = token_length_statistics(train + validation, tokenizer)
    if stats["exceeding_2048"]:
        raise ValueError("Training examples exceed max_seq_length; refusing silent truncation")
    verify_assistant_only_mask(train[0], tokenizer)
    from datasets import Dataset
    from transformers import Trainer, TrainerCallback, TrainingArguments
    encoded_train = Dataset.from_list([assistant_only_tokens(example, tokenizer) for example in train])
    _validate_smoke_example(encoded_train[0])
    output_root = stage4_output_root(config)
    output_root.mkdir(parents=True, exist_ok=True)
    diagnostics = _GradientDiagnostics(TrainerCallback)
    validation_history_path = output_root / "validation_history.json"
    validation_history = load_validation_history(validation_history_path, not config.no_resume)

    class ValidationCallback(TrainerCallback):
        def on_epoch_end(self, args, state, control, model=None, **kwargs):
            model.config.use_cache = True
            raw_outputs = _generate(model, tokenizer, validation, 192)
            result = evaluate_validation_predictions(validation, raw_outputs)
            epoch = int(round(state.epoch))
            adapter_dir = output_root / f"epoch_{epoch}_adapter"
            model.save_pretrained(adapter_dir)
            upsert_validation_history(validation_history, {"epoch": epoch, **_metric_summary(result)})
            persist_validation_history(validation_history_path, validation_history)
            model.config.use_cache = False
            return control

    args = TrainingArguments(output_dir=str(output_root / "work"), num_train_epochs=config.epochs,
        per_device_train_batch_size=config.train_batch_size, gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate, warmup_ratio=config.warmup_ratio, lr_scheduler_type=config.scheduler,
        logging_steps=1, save_strategy="steps", save_steps=5, save_total_limit=2, report_to=[],
        fp16=hardware["fp16"], bf16=hardware["bf16"],
        optim=config.optimizer, gradient_checkpointing=config.gradient_checkpointing, seed=config.seed)
    trainer = Trainer(model=model, args=args, train_dataset=encoded_train,
                      data_collator=_Collator(tokenizer, config.max_seq_length),
                      callbacks=[diagnostics.callback, ValidationCallback()])
    checkpoint = checkpoint_for_resume(output_root / "work", config.no_resume)
    if checkpoint is not None:
        print(f"Resuming Stage 4 from checkpoint: {checkpoint}")
        result = trainer.train(resume_from_checkpoint=str(checkpoint))
    else:
        result = trainer.train()
    expected_epochs = list(range(1, config.epochs + 1))
    actual_epochs = [int(entry["epoch"]) for entry in validation_history]
    if actual_epochs != expected_epochs:
        raise RuntimeError("validation history does not contain each training epoch exactly once")
    if not all(math.isfinite(float(entry["loss"])) for entry in trainer.state.log_history if "loss" in entry):
        raise RuntimeError("training loss became non-finite")
    amp_classification = classify_amp_records(diagnostics.callback.records)
    if amp_classification["persistent_after_recovery"]:
        raise RuntimeError("non-finite gradients persisted after initial scaler recovery")
    best = select_best_validation(validation_history)
    training_history = list(trainer.state.log_history)
    best_dir = output_root / "best_adapter"
    import shutil
    if best_dir.exists():
        shutil.rmtree(best_dir)
    shutil.copytree(output_root / f"epoch_{best['epoch']}_adapter", best_dir)
    model.config.use_cache = True
    del trainer, model
    gc.collect()
    import torch
    torch.cuda.empty_cache()
    reloaded, reload_tokenizer, _, _ = load_quantized_model(config)
    reloaded.load_adapter(str(best_dir), adapter_name="default")
    final_result = evaluate_validation_predictions(validation,
        _generate(reloaded, reload_tokenizer, validation, 192))
    final_metrics = _metric_summary(final_result)
    if final_metrics["normalized_macro_field_accuracy"] != best["normalized_macro_field_accuracy"]:
        raise RuntimeError("reloaded best adapter did not reproduce selected validation result")
    versions = {}
    from importlib.metadata import version
    for package in ("torch", "transformers", "peft", "bitsandbytes"):
        try:
            versions[package] = version(package)
        except Exception:
            versions[package] = "unavailable"
    metadata = {"model_id": config.model_id, "model_revision": config.model_revision,
        "dataset_id": config.dataset_id, "seed": config.seed, "cuda_version": hardware["cuda_version"],
        "gpu": hardware["device"], "versions": versions, "qlora": {"r": config.lora_r, "alpha": config.lora_alpha,
        "dropout": config.lora_dropout, "target_modules": list(config.target_modules), "nf4": True, "double_quantization": True,
        "compute_dtype": str(hardware["compute_dtype"])}, "training_config": config.__dict__,
        "train_examples": len(train), "validation_examples": len(validation), "token_statistics": stats,
        "validation_history": validation_history, "best_epoch": best["epoch"], "best_validation": best,
        "reloaded_best_validation": final_metrics, "official_test_split_loaded": False,
        "amp_diagnostics": {"records": diagnostics.callback.records, "classification": amp_classification,
        "optimizer_callback_events": diagnostics.callback.step_events,
        "effective_parameter_updates": sum(event.get("weight_sample_changed", False) for event in diagnostics.callback.step_events)},
        "training_loss": result.training_loss, "runtime_seconds": time.perf_counter() - started}
    (output_root / "training_history.json").write_text(json.dumps(training_history, indent=2) + "\n", encoding="utf-8")
    persist_validation_history(validation_history_path, validation_history)
    (output_root / "training_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    del reloaded
    gc.collect()
    torch.cuda.empty_cache()
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    if args.smoke == args.train:
        raise SystemExit("choose exactly one of --smoke or --train")
    config = TrainingConfig(no_resume=args.no_resume)
    print(json.dumps(smoke_test(config) if args.smoke else full_train(config), indent=2))


if __name__ == "__main__":
    main()

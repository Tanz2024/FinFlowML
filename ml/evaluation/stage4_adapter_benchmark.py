"""Evaluate the pinned base model and a pre-trained LoRA adapter on SROIE test.

This module intentionally contains no training code.  It uses the official
test split only for final reporting; train/validation examples are inspected
only for split-integrity metadata.
"""

import argparse
import hashlib
import json
import os
import platform
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from statistics import mean, median

from ml.data.constants import DATASET_ID, DEFAULT_SEED, TARGET_FIELDS
from ml.data.split import split_examples
from ml.data.sroie import load_sroie_dataset, process_split
from ml.evaluation.metrics import metrics
from ml.extraction.parser import parse_prediction
from ml.extraction.prompt import build_prompt
from ml.modeling.loader import load_finflow_model, validate_adapter_path

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"


def _package_versions(names: tuple[str, ...]) -> dict[str, str]:
    result = {}
    for name in names:
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = "unavailable"
    return result


def _hardware() -> dict[str, object]:
    import torch

    cuda = torch.cuda.is_available()
    result: dict[str, object] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch_device": "cuda" if cuda else "cpu",
        "cuda_available": cuda,
        "cuda_version": torch.version.cuda,
    }
    if cuda:
        result.update(
            {
                "device_name": torch.cuda.get_device_name(0),
                "device_index": 0,
                "bf16_supported": torch.cuda.is_bf16_supported(),
                "memory_allocated_bytes_before": torch.cuda.memory_allocated(0),
                "memory_reserved_bytes_before": torch.cuda.memory_reserved(0),
            }
        )
    return result


def _near_duplicate_report(splits: dict[str, list]) -> dict[str, object]:
    """Report exact fingerprint overlap and conservative text near-overlap."""
    fingerprints = {name: {item.fingerprint for item in values} for name, values in splits.items()}
    exact = {}
    near = {}
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        overlap = sorted(fingerprints[left] & fingerprints[right])
        exact[f"{left}_vs_{right}"] = overlap
        pairs = []
        for left_item in splits[left]:
            left_text = " ".join(left_item.raw_targets.values()).casefold()
            for right_item in splits[right]:
                right_text = " ".join(right_item.raw_targets.values()).casefold()
                if left_text and right_text and SequenceMatcher(None, left_text, right_text).ratio() >= 0.98:
                    pairs.append(
                        {
                            "left": left_item.example_id,
                            "right": right_item.example_id,
                            "ratio": SequenceMatcher(None, left_text, right_text).ratio(),
                        }
                    )
        near[f"{left}_vs_{right}"] = pairs
    return {"exact_fingerprint_overlap": exact, "near_target_text_overlap_ge_0.98": near}


def _dataset_integrity(dataset_id: str, dataset_revision: str | None = None) -> dict[str, object]:
    dataset = load_sroie_dataset(dataset_id, revision=dataset_revision)
    official_test = process_split(dataset["test"], "test")
    source_train = process_split(dataset["train"], "source_train")
    train, validation = split_examples(source_train, seed=DEFAULT_SEED)
    splits = {"train": train, "validation": validation, "test": official_test}
    return {
        "dataset_id": dataset_id,
        "seed": DEFAULT_SEED,
        "counts": {name: len(values) for name, values in splits.items()},
        "split_fingerprints": {
            name: hashlib.sha256("\n".join(sorted(item.fingerprint for item in values)).encode()).hexdigest()
            for name, values in splits.items()
        },
        "overlap": _near_duplicate_report(splits),
        "official_test_split_used_for_training_or_selection": False,
    }


def _load_for_eval(adapter_path: Path | None, compute_dtype, device_map):
    from transformers import BitsAndBytesConfig

    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=compute_dtype,
    )
    return load_finflow_model(
        MODEL_ID,
        adapter_path,
        quantization_config=quantization,
        device_map=device_map,
        revision=MODEL_REVISION,
        torch_dtype=compute_dtype,
    )


def _write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _adapter_signature(adapter_path: Path) -> dict[str, object]:
    files = []
    for name in ("adapter_config.json", "adapter_model.safetensors", "adapter_model.bin"):
        path = adapter_path / name
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            files.append({"name": name, "size": path.stat().st_size, "sha256": digest.hexdigest()})
    return {"path": str(adapter_path.resolve()), "files": files}


def _load_checkpoint(path: Path, manifest: dict[str, object], resume: bool) -> list[dict]:
    if not resume or not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("manifest") != manifest:
        raise ValueError(f"checkpoint manifest mismatch: {path}")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError(f"checkpoint records are not a list: {path}")
    return records


def _evaluate_model(
    loaded,
    examples,
    rows,
    label: str,
    max_new_tokens: int,
    checkpoint_path: Path,
    manifest: dict[str, object],
    resume: bool,
) -> tuple[dict, list[dict]]:
    records = _load_checkpoint(checkpoint_path, manifest, resume)
    expected_ids = [item.example_id for item in examples[: len(records)]]
    if [item["example_id"] for item in records] != expected_ids:
        raise ValueError(f"checkpoint document identities do not match current test split: {checkpoint_path}")
    for example in examples[len(records) :]:
        ocr_text = " ".join(rows[example.index]["words"])
        rendered = loaded.tokenizer.apply_chat_template(
            [{"role": "user", "content": build_prompt(ocr_text)}],
            add_generation_prompt=True,
            tokenize=False,
        )
        inputs = loaded.tokenizer(rendered, return_tensors="pt")
        device = getattr(loaded.model, "device", None)
        if device is not None:
            inputs = inputs.to(device)
        started = time.perf_counter()
        with __import__("torch").inference_mode():
            output = loaded.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        elapsed = time.perf_counter() - started
        generated = output[0][inputs["input_ids"].shape[-1] :]
        raw = loaded.tokenizer.decode(generated, skip_special_tokens=True).strip()
        prediction, parse_error = parse_prediction(raw)
        score = metrics(example.raw_targets, prediction or {})
        records.append(
            {
                "example_id": example.example_id,
                "fingerprint": example.fingerprint,
                "raw_model_output": raw,
                "prediction": prediction,
                "parse_error": parse_error,
                "invalid_output": parse_error is not None,
                "latency_seconds": elapsed,
                "scores": score,
            }
        )
        _write_json(checkpoint_path, {"manifest": manifest, "model_label": label, "records": records})
    summary = {
        "model_label": label,
        "documents": len(records),
        "json_validity_rate": sum(not item["invalid_output"] for item in records) / len(records),
        "field_accuracy": {
            field: mean(item["scores"]["normalized_exact_match"][field] for item in records)
            for field in TARGET_FIELDS
        },
        "macro_field_accuracy": mean(item["scores"]["macro_field_accuracy"] for item in records),
        "all_fields_correct_rate": mean(item["scores"]["document_all_fields_correct"] for item in records),
        "latency_seconds": {
            "mean": mean(item["latency_seconds"] for item in records),
            "median": median(item["latency_seconds"] for item in records),
            "min": min(item["latency_seconds"] for item in records),
            "max": max(item["latency_seconds"] for item in records),
            "total": sum(item["latency_seconds"] for item in records),
        },
        "error_breakdown": {
            "invalid_json_or_schema": sum(item["invalid_output"] for item in records),
            "documents_with_any_incorrect_field": sum(
                not item["scores"]["document_all_fields_correct"] for item in records
            ),
        },
    }
    return summary, records


def run(
    adapter_path: Path,
    output_dir: Path,
    dataset_id: str = DATASET_ID,
    max_new_tokens: int = 192,
    dataset_revision: str | None = None,
    resume: bool = False,
) -> dict:
    validate_adapter_path(adapter_path)
    integrity = _dataset_integrity(dataset_id, dataset_revision)
    if integrity["counts"]["test"] != 347:
        raise ValueError(f"expected 347 official test examples, got {integrity['counts']['test']}")
    if any(integrity["overlap"]["exact_fingerprint_overlap"].values()):
        raise ValueError("exact fingerprint overlap detected across evaluation splits")

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("This benchmark requires CUDA for 4-bit bitsandbytes loading")
    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    device_map = {"": 0}
    dataset = load_sroie_dataset(dataset_id, revision=dataset_revision)
    examples = process_split(dataset["test"], "test")
    rows = dataset["test"].remove_columns(["image"])
    document_identities = [
        {"example_id": item.example_id, "fingerprint": item.fingerprint} for item in examples
    ]
    common = {
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_integrity": {
            **integrity,
            "dataset_revision": dataset_revision or "not supplied",
            "official_test_split_historical_training_or_selection_verified": False,
            "code_path_test_split_isolated": True,
        },
        "base_model": {"id": MODEL_ID, "revision": MODEL_REVISION},
        "adapter": {
            "provenance": "pre-trained Colab Stage 4 best epoch 3",
            "signature": _adapter_signature(adapter_path),
        },
        "evaluation": {"max_new_tokens": max_new_tokens, "do_sample": False, "prompt": "ml/extraction/prompt.py", "normalization": "ml/data/normalize.py", "metrics": "ml/evaluation/metrics.py"},
        "packages": _package_versions(("torch", "transformers", "peft", "bitsandbytes", "datasets", "safetensors")),
        "hardware": _hardware(),
    }
    manifest = {
        "base_model": common["base_model"],
        "adapter": common["adapter"],
        "dataset_id": dataset_id,
        "dataset_revision": dataset_revision or "not supplied",
        "split_fingerprints": integrity["split_fingerprints"],
        "document_identities": document_identities,
        "evaluation": common["evaluation"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "evaluation_manifest.json"
    if manifest_path.is_file() and not resume:
        raise FileExistsError(f"output already contains a manifest; use --resume: {output_dir}")
    if resume and manifest_path.is_file():
        saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if saved_manifest != manifest:
            raise ValueError("evaluation manifest mismatch; refusing unsafe resume")
    _write_json(manifest_path, manifest)
    base = _load_for_eval(None, compute_dtype, device_map)
    base_summary, base_records = _evaluate_model(
        base,
        examples,
        rows,
        "base",
        max_new_tokens,
        output_dir / "base_predictions.partial.json",
        manifest,
        resume,
    )
    del base
    torch.cuda.empty_cache()
    adapter = _load_for_eval(adapter_path, compute_dtype, device_map)
    adapter_summary, adapter_records = _evaluate_model(
        adapter,
        examples,
        rows,
        "adapter",
        max_new_tokens,
        output_dir / "adapter_predictions.partial.json",
        manifest,
        resume,
    )
    paired = []
    for before, after in zip(base_records, adapter_records, strict=True):
        paired.append(
            {
                "example_id": before["example_id"],
                "fingerprint": before["fingerprint"],
                "base_macro_accuracy": before["scores"]["macro_field_accuracy"],
                "adapter_macro_accuracy": after["scores"]["macro_field_accuracy"],
                "macro_delta": after["scores"]["macro_field_accuracy"] - before["scores"]["macro_field_accuracy"],
                "base_all_fields_correct": before["scores"]["document_all_fields_correct"],
                "adapter_all_fields_correct": after["scores"]["document_all_fields_correct"],
                "fields_improved": [f for f in TARGET_FIELDS if after["scores"]["normalized_exact_match"][f] and not before["scores"]["normalized_exact_match"][f]],
                "fields_regressed": [f for f in TARGET_FIELDS if before["scores"]["normalized_exact_match"][f] and not after["scores"]["normalized_exact_match"][f]],
            }
        )
    report = {**common, "base_summary": base_summary, "adapter_summary": adapter_summary, "paired_summary": {"documents_improved": sum(item["macro_delta"] > 0 for item in paired), "documents_regressed": sum(item["macro_delta"] < 0 for item in paired), "mean_macro_delta": mean(item["macro_delta"] for item in paired)}, "paired_documents": paired}
    _write_json(output_dir / "report.json", report)
    _write_json(output_dir / "base_predictions.json", base_records)
    _write_json(output_dir / "adapter_predictions.json", adapter_records)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("results/stage4_evaluation"))
    parser.add_argument("--dataset-id", default=DATASET_ID)
    parser.add_argument("--dataset-revision", help="Hugging Face dataset commit/revision used for this run")
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    report = run(args.adapter, args.output, args.dataset_id, args.max_new_tokens, args.dataset_revision, args.resume)
    print(json.dumps({"output": str(args.output), "base": report["base_summary"], "adapter": report["adapter_summary"]}, indent=2))


if __name__ == "__main__":
    main()

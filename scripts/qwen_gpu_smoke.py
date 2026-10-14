"""Evidence-producing smoke test for the pinned real OCR + Qwen LoRA path.

This script requires a CUDA environment, PaddleOCR, the pinned base revision,
and a readable adapter. It never trains or changes adapter files.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _log(message: str) -> None:
    print(f"[qwen-smoke] {message}", file=sys.stderr, flush=True)


REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_stage(command: list[str], stage: str, result_path: Path) -> tuple[dict, float]:
    _log(f"stage={stage} start")
    started = time.monotonic()
    child_env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    result = subprocess.run(command + ["--result", str(result_path)], capture_output=True,
                            text=True, check=False, env=child_env)
    duration = time.monotonic() - started
    if result.stdout:
        print(result.stdout, file=sys.stderr, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode:
        raise RuntimeError(f"stage={stage} failed exit_code={result.returncode}")
    if not result_path.is_file():
        raise RuntimeError(f"stage={stage} did not produce result file: {result_path}")
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"stage={stage} emitted invalid result file: {exc}") from exc
    _log(f"stage={stage} complete seconds={duration:.3f}")
    return payload, duration


def _write_result(result_path: Path, payload: dict) -> None:
    result_path.write_text(json.dumps(payload), encoding="utf-8")


def _ocr_stage(image: str, result_path: Path) -> None:
    from ml.ocr.extract import extract_text
    print("[qwen-smoke] OCR worker loaded", flush=True)
    _write_result(result_path, {"ocr_text": extract_text(image)})


def _model_stage(args: argparse.Namespace) -> None:
    import torch

    from ml.inference.predict import (
        build_quantization_config,
        generate_prediction,
        load_inference_model,
    )
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required; no real-model evidence produced")
    ocr_text = json.loads(args.ocr_json.read_text(encoding="utf-8"))["ocr_text"]
    started = time.monotonic()
    loaded = load_inference_model(args.base_model, args.adapter, revision=args.revision,
                                  device_map="auto", quantization_config=build_quantization_config())
    load_seconds = time.monotonic() - started
    raw_output, prediction, parsing_error = generate_prediction(
        loaded, ocr_text, max_new_tokens=args.max_new_tokens)
    _write_result(args.result, {"cuda": True, "base_model": args.base_model, "revision": args.revision,
                                "adapter_loaded": bool(getattr(loaded.model, "peft_config", {})),
                                "model_load_seconds": round(load_seconds, 3), "ocr_chars": len(ocr_text),
                                "prediction": prediction, "parsing_error": parsing_error, "raw_output": raw_output})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image")
    parser.add_argument("--adapter")
    parser.add_argument("--base-model", default="Qwen/Qwen3-4B-Instruct-2507")
    parser.add_argument("--revision", default="cdbee75f17c01a7cc42f958dc650907174af0554")
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--_stage", choices=("ocr", "model"))
    parser.add_argument("--ocr-json", type=Path)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    if args._stage == "ocr":
        _ocr_stage(args.image, args.result); return 0
    if args._stage == "model":
        _model_stage(args); return 0
    evidence = {"status": "failed", "image": args.image, "adapter_path": args.adapter}
    started = time.monotonic()
    try:
        if not args.image or not args.adapter:
            raise ValueError("--image and --adapter are required")
        adapter = Path(args.adapter)
        if not (adapter / "adapter_config.json").is_file():
            raise ValueError(f"Missing adapter_config.json: {adapter}")
        with tempfile.TemporaryDirectory(prefix="finflow-qwen-smoke-") as temp_dir:
            temp_root = Path(temp_dir)
            ocr_json = temp_root / "ocr.json"
            ocr_result = temp_root / "ocr-result.json"
            model_result = temp_root / "model-result.json"
            ocr_payload, ocr_seconds = _run_stage([sys.executable, str(Path(__file__).resolve()), "--_stage", "ocr", "--image", args.image], "ocr", ocr_result)
            ocr_json.write_text(json.dumps(ocr_payload), encoding="utf-8")
            model_payload, model_seconds = _run_stage([sys.executable, str(Path(__file__).resolve()), "--_stage", "model", "--adapter", args.adapter,
            "--base-model", args.base_model, "--revision", args.revision, "--max-new-tokens", str(args.max_new_tokens),
            "--ocr-json", str(ocr_json)], "model", model_result)
            if not model_payload.get("cuda") or not model_payload.get("adapter_loaded"):
                raise RuntimeError("model stage did not confirm CUDA and adapter loading")
            if not isinstance(model_payload.get("prediction"), dict) or model_payload.get("parsing_error") is not None:
                raise RuntimeError("model stage did not produce a valid prediction")
            evidence.update(model_payload, ocr_seconds=round(ocr_seconds, 3), model_seconds=round(model_seconds, 3), status="passed")
    except Exception as exc:
        evidence.update(error_type=type(exc).__name__, error=str(exc)); _log(str(exc))
    evidence["total_seconds"] = round(time.monotonic() - started, 3)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, default=str))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

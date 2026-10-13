"""Evidence-producing smoke test for the pinned real OCR + Qwen LoRA path.

This script requires a CUDA environment, PaddleOCR, the pinned base revision,
and a readable adapter. It never trains or changes adapter files.
"""

import argparse
import json
import time
from pathlib import Path

import torch

from ml.inference.predict import load_inference_model, predict_image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--base-model", default="Qwen/Qwen3-4B-Instruct-2507")
    parser.add_argument("--revision", default="cdbee75f17c01a7cc42f958dc650907174af0554")
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required; no real-model evidence produced")
    adapter = Path(args.adapter)
    if not (adapter / "adapter_config.json").is_file():
        raise SystemExit(f"Missing adapter_config.json: {adapter}")
    started = time.monotonic()
    loaded = load_inference_model(args.base_model, str(adapter), revision=args.revision, device_map="auto")
    first_load_seconds = time.monotonic() - started
    model_is_peft = hasattr(loaded.model, "peft_config") and bool(loaded.model.peft_config)
    started = time.monotonic()
    ocr_text, raw_output, prediction, parsing_error = predict_image(args.image, args.base_model, str(adapter), revision=args.revision)
    print(json.dumps({"cuda": True, "adapter_path": str(adapter), "adapter_loaded": model_is_peft, "base_model": args.base_model, "revision": args.revision, "first_load_seconds": round(first_load_seconds, 3), "inference_seconds": round(time.monotonic() - started, 3), "ocr_chars": len(ocr_text), "prediction": prediction, "parsing_error": parsing_error, "raw_output": raw_output}, default=str, indent=2))


if __name__ == "__main__":
    main()

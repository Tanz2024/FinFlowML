"""Fail-fast checks for the real GPU worker image; no model weights are loaded."""
import importlib

import torch

required = ("paddle", "paddleocr", "bitsandbytes", "transformers", "peft")
for name in required:
    importlib.import_module(name)
if not torch.cuda.is_available():
    raise SystemExit("CUDA is unavailable")
print({"cuda": torch.version.cuda, "device": torch.cuda.get_device_name(0), "dependencies": required})

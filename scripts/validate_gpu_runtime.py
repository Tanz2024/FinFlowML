"""Fail-fast checks for the real GPU worker image; no model weights are loaded."""
import importlib
import importlib.metadata

import torch

required = ("paddle", "paddleocr", "bitsandbytes", "transformers", "peft")
for name in required:
    importlib.import_module(name)
if not torch.cuda.is_available():
    raise SystemExit("CUDA is unavailable")
print({
    "cuda": torch.version.cuda,
    "cudnn": torch.backends.cudnn.version(),
    "device": torch.cuda.get_device_name(0),
    "torch": importlib.metadata.version("torch"),
    "paddle": importlib.metadata.version("paddlepaddle-gpu"),
    "dependencies": required,
})

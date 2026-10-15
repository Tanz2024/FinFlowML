# Stage 8 Camber GPU benchmark

This benchmark is standalone: it does not start Docker Compose, FastAPI, or
PostgreSQL. It loads the pinned Qwen model once, attaches the existing
read-only LoRA adapter, runs the existing PaddleOCR and parser path, and emits
sanitized `results.json` and `results.csv`. It never writes OCR text, raw model
output, receipt paths, expected values, credentials, adapter weights, or model
weights to the result files.

Prepare two separate local manifests. The first contains 5–10 synthetic smoke
receipts; the second contains 30–50 independent, never-seen receipts. Each is
a JSON list with local image paths and expected fields, for example:

```json
[{"image":"/job/smoke/receipt-01.png","expected":{"company":"DEMO CAFE SDN BHD","date":"15/10/2026","address":"123 TEST ROAD KUALA LUMPUR","total":"MYR 12.50"}}]
```

## Camber Nova commands

Use a free NVIDIA L4 job only; do not place the adapter, receipts, or manifests
in GitHub. Mount them through Camber’s private secret/object-storage mechanism
or copy them over an authorized private channel. The exact storage command is
platform-specific, so verify the resulting paths before running:

```bash
git clone https://github.com/Tanz2024/FinFlowML.git
cd FinFlowML
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-training.txt
python -m pip install paddleocr paddlepaddle torch==2.6.0 \
  --index-url https://download.pytorch.org/whl/cu124 \
  --extra-index-url https://pypi.org/simple
nvidia-smi
test -r "$ADAPTER_PATH/adapter_config.json"
test -r "$ADAPTER_PATH/adapter_model.safetensors"
```

Run the two sets independently, writing results outside the repository:

```bash
python scripts/camber_receipt_benchmark.py \
  --manifest /private/manifest-smoke.json \
  --adapter "$ADAPTER_PATH" \
  --output-dir /private/results-smoke

python scripts/camber_receipt_benchmark.py \
  --manifest /private/manifest-independent.json \
  --adapter "$ADAPTER_PATH" \
  --output-dir /private/results-independent
```

The script refuses a non-CUDA runtime or an unpinned model revision. The
summary records JSON validity, parsing errors, per-field accuracy,
all-fields-correct count, cold model load time, warm per-receipt inference
latency, OCR latency and peak allocated VRAM. A successful script execution is
not a benchmark success until the result files are reviewed and the expected
receipt sets are confirmed independent.

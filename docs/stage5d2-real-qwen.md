# Stage 5D.2: real Qwen adapter demonstration

This repository contains the real path but no local CUDA evidence. The MacBook mock path and unit tests do not prove Qwen inference. A live demonstration must be run in a CUDA-capable Colab runtime and its output retained separately.

## GPU smoke test

In a fresh Colab T4 runtime, mount Drive, clone the pushed commit, install the training/inference dependencies plus PaddleOCR, and use the existing read-only adapter:

```bash
git clone https://github.com/Tanz2024/FinFlowML.git /content/FinFlowML
cd /content/FinFlowML
git checkout cc7fad0
pip install -r requirements-training.txt paddleocr paddlepaddle
python scripts/qwen_gpu_smoke.py \
  --image /content/receipt.jpg \
  --adapter /content/drive/MyDrive/FinFlowML-stage4-final-v2/best_adapter
```

The JSON output must show `cuda: true`, `adapter_loaded: true`, the pinned base revision `cdbee75f17c01a7cc42f958dc650907174af0554`, OCR characters greater than zero, and measured load/inference latency. Do not call this a successful live demonstration until those lines are produced by Colab.

## End-to-end isolated workflow

Use a separate PostgreSQL database and local-only API endpoint. Set `DATABASE_URL`, `AUTH_SECRET`, `MODEL_ID`, `MODEL_REVISION`, and `ADAPTER_PATH`; run migrations, bootstrap an account, then start API and GPU worker as separate processes:

```bash
alembic -c backend/alembic.ini upgrade head
python -m backend.bootstrap
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
python -m backend.worker
```

Submit an image with an authenticated `Idempotency-Key`, poll `/jobs/{job_id}`, inspect the raw extraction, correct missing/invalid values through the review endpoint, and approve. Approval creates one expense and corresponding audit events. Missing currency, invalid dates, malformed JSON, failed OCR, and missing fields must remain review/failure states; the worker must never invent values.

The worker caches one base/tokenizer/adapter load per process and renews the job lease through a separate SQLAlchemy session while model loading and inference run. Adapter weights are read-only. `FINFLOW_MOCK_EXTRACTION=true` remains available only for local deterministic tests and is not real AI inference.

# Stage 6D GPU worker validation

This procedure requires a Linux host with Docker, NVIDIA Container Toolkit,
the pinned adapter available outside the repository, and a private PostgreSQL
stack. The image performs CUDA/dependency checks only when the GPU worker starts;
image builds do not require a GPU.

## Build and start

```bash
docker compose build
docker compose up -d db
docker compose run --rm migrations
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build gpu-worker
ADAPTER_PATH=/private/path/to/best_adapter \
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml \
  --profile gpu up -d gpu-worker
docker compose ps
```

The GPU entrypoint runs `scripts/validate_gpu_runtime.py` before starting the
worker. It reports CUDA, cuDNN, PyTorch, PaddlePaddle GPU, device, Transformers,
PEFT, and bitsandbytes availability. A failed check stops the worker; there is
no production mock fallback.

## End-to-end evidence

Run the authenticated workflow smoke with a known receipt image:

```bash
SMOKE_EMAIL=reviewer@example.com \
SMOKE_PASSWORD='disposable-test-password' \
SMOKE_IMAGE=/private/path/to/receipt.jpg \
./scripts/container_smoke.sh
```

Record only sanitized evidence: model ID, pinned revision, adapter fingerprint,
CUDA/device status, job state, OCR/generation/total timings, peak VRAM/RAM, and
pass/fail results. Do not record tokens, OCR text, raw model output, receipt
images, or credentials in operational logs.

## Required acceptance checks

Verify one approved receipt creates exactly one expense, repeated approval is
idempotent, rejection creates none, raw extraction snapshots are unchanged,
tenant isolation holds, and a worker restart recovers leased jobs. Run the
Playwright suite against the private API after the container smoke passes.

This repository has not executed these Docker/GPU commands on the current host
because Docker and NVIDIA hardware are unavailable. Prior Colab inference does
not validate this containerized production path.

# Stage 7B: real Qwen/LoRA inference validation

The repository contains the real inference path, but the adapter is an external
artifact and must never be committed. The expected authorized Drive folder is:

`MyDrive/FinFlowML-stage4-final-v2/best_adapter/`

It must contain `adapter_config.json`, `adapter_model.safetensors`, and
`README.md`. The current macOS ARM development host has no NVIDIA runtime,
and the connected Drive account was not available during this validation.
Standalone Colab inference has since been confirmed by the project owner with
the following sanitized result: `status=passed`, `cuda=true`,
`adapter_loaded=true`, `parsing_error=null`, OCR characters `103`, OCR time
`7.517s`, cold model load `365.34s`, total `394.512s`, company `DEMO CAFE SDN
BHD`, date `15/10/2026`, address `123 TEST ROAD KUALA LUMPUR`, and total
`MYR 12.50`. This is a standalone acceptance result only; GPU Docker worker
integration remains **NOT TESTED**, so full Stage 7B remains blocked.

## Recover and validate the adapter in Colab

Use a fresh NVIDIA Colab runtime. This cell only reads the adapter and writes
sanitized evidence; it does not train or alter the adapter.

```python
from google.colab import drive
drive.mount('/content/drive')

import hashlib, json, os, subprocess, sys
from pathlib import Path

repo = Path('/content/FinFlowML')
subprocess.run(['git', 'clone', 'https://github.com/Tanz2024/FinFlowML.git', str(repo)], check=True)
os.chdir(repo)
subprocess.run(['git', 'checkout', '3271e5ce38cf25f51621ce76b0a16eb828bf652e'], check=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements-training.txt',
                'paddleocr', 'paddlepaddle'], check=True)

adapter = Path('/content/drive/MyDrive/FinFlowML-stage4-final-v2/best_adapter')
assert (adapter / 'adapter_config.json').is_file()
weights = adapter / 'adapter_model.safetensors'
assert weights.is_file(), weights
config = json.loads((adapter / 'adapter_config.json').read_text())
fingerprint = hashlib.sha256(weights.read_bytes()).hexdigest()
print(json.dumps({
    'adapter': str(adapter),
    'weight_bytes': weights.stat().st_size,
    'weight_sha256': fingerprint,
    'base_model_name_or_path': config.get('base_model_name_or_path'),
    'peft_type': config.get('peft_type'),
    'r': config.get('r'),
    'lora_alpha': config.get('lora_alpha'),
}, indent=2))
```

The configuration must identify the Qwen base architecture and be compatible
with `Qwen/Qwen3-4B-Instruct-2507`. The pinned base revision is:

`cdbee75f17c01a7cc42f958dc650907174af0554`

Run the isolated smoke test with a synthetic or otherwise authorized receipt:

```bash
python scripts/qwen_gpu_smoke.py \
  --image /content/receipt.jpg \
  --adapter /content/drive/MyDrive/FinFlowML-stage4-final-v2/best_adapter \
  --evidence /content/drive/MyDrive/FinFlowML-stage7b-evidence.json
```

Accept evidence only when it contains `status: passed`, `cuda: true`,
`adapter_loaded: true`, `prediction_valid: true`, `parsing_error: null`,
positive OCR character count, the pinned model revision, and measured stage
timings. The smoke test now omits raw model output and extracted values from
evidence by default. Use `--include-debug-output` only for a controlled local
diagnostic that must not be uploaded or retained as operational evidence.
Do not store raw OCR text, generated output, receipt images, credentials, or
tokens in operational logs.

## GPU worker validation

The standalone smoke test and the containerized worker are separate acceptance
gates. On a Linux host with NVIDIA Container Toolkit, a readable external
adapter, and private PostgreSQL:

```bash
export ADAPTER_PATH=/private/path/to/best_adapter
docker compose build
docker compose up -d db
docker compose run --rm migrations
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu build gpu-worker
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu up -d gpu-worker
docker compose -f docker-compose.yml -f docker-compose.gpu.yml \
  exec gpu-worker python /app/scripts/validate_gpu_runtime.py
```

The GPU profile sets `FINFLOW_MOCK_EXTRACTION=false`, mounts the adapter
read-only at `/models/adapter`, pins the model revision above, and uses the
private Compose network. Do not start the CPU/mock worker against the same
database while the GPU worker is processing jobs. The model cache must either
be preloaded into the `hf_cache` volume or be populated through an explicitly
approved controlled download phase.

The current GPU Docker and worker path has not been executed on the development
host. Successful historical Colab inference does not validate this container
integration gate.

## GPU image dependency preflight

`Dockerfile.gpu` uses Python 3.11, the CUDA 12.4 PyTorch 2.6.0 wheel index,
and PaddlePaddle-GPU 3.3.0 from the official CUDA 12.6 package index. The
shared `sympy==1.14.0` pin is deliberately replaced in the GPU build with
`sympy==1.13.1`, which is the compatible PyTorch 2.6.0 dependency. The image
build combines these requirements and resolves dependencies normally; it does
not use `--no-deps`.

The build-only preflight can be run without a GPU:

```bash
docker build --file Dockerfile.gpu --tag finflowml-gpu-preflight:local .
```

The repository also provides a manual GitHub Actions build-only workflow at
`.github/workflows/gpu-image-build.yml`. A successful build proves only Linux
package and image resolution. It does not prove NVIDIA driver access, CUDA
initialization, model loading, OCR, or application-worker inference. The
development Mac cannot execute this build locally when Docker is unavailable;
the workflow must be run before treating the image as build-verified.

## Disposable PostgreSQL regression run

The CPU regression workflow starts an isolated PostgreSQL 16 service container,
applies Alembic migrations to `finflowml_test`, and runs the PostgreSQL worker,
approval-idempotency, and invoice-lock tests using only CI-created data. It has
no access to production databases or volumes. To reproduce the same checks
locally with a disposable container:

```bash
docker run --rm --name finflowml-pg-test \
  -e POSTGRES_USER=finflowml -e POSTGRES_PASSWORD=ci-only-password \
  -e POSTGRES_DB=finflowml_test -p 5432:5432 -d postgres:16
export DATABASE_URL=postgresql+psycopg://finflowml:ci-only-password@localhost:5432/finflowml_test
export FINFLOW_POSTGRES_TEST_URL="$DATABASE_URL"
python -m alembic upgrade head
python -m pytest -q backend/tests/test_postgres_integration.py
docker rm -f finflowml-pg-test
```

This is separate from GPU acceptance and does not execute model inference.

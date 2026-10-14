# FinFlowML

Stage 1 provides a FastAPI/PostgreSQL foundation, SQLAlchemy 2 models, Alembic migrations, core endpoints, tests, and read-only SROIE inspection.

## Dataset & Evaluation

Stage 2 uses the public Hugging Face mirror `mp-02/sroie` currently used by FinFlowML. It is not presented as an official Hugging Face dataset ID. The dataset exposes `image`, `words`, `ner_tags`, and `bboxes`, with labels `S-COMPANY`, `S-DATE`, `S-ADDRESS`, `S-TOTAL`, and `O`. The official `test` split is kept untouched; the 626-example training split is deterministically divided into train and validation.

Generate safe processed metadata and statistics with:

```bash
python -m ml.data.build_metadata
```

This writes ignored metadata under `data/processed/` and preserves raw and normalized extraction targets without serializing image bytes.

## Stage 3 baseline benchmark

The baseline benchmark uses the instruction-tuned `Qwen/Qwen3-4B-Instruct-2507` model with OCR text only. It does not train or fine-tune model weights. The same model is reserved for Stage 4 LoRA/QLoRA comparison. After installing requirements, run the required smoke tests in order:

```bash
python -m ml.evaluation.benchmark --limit 3
python -m ml.evaluation.benchmark --limit 10
```

Outputs are ignored under `results/baseline/` and include exact raw model responses, parsed predictions, inference times, runtime metadata, metrics, and error analysis fields. A full 347-document benchmark is intentionally not run during Stage 3 implementation.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cd backend && alembic upgrade head && cd ..
uvicorn backend.app.main:app --reload
pytest
ruff check .
```

Run the dataset inspector with `python ml/data/load_sroie.py`.

## Stage 5 frontend demo

The minimal receipt demo connects an image upload to the existing OCR → QLoRA
inference → parser pipeline. Start the API from the repository root:

```bash
uvicorn backend.app.main:app --reload
```

Open <http://127.0.0.1:8000/demo> and choose a receipt image. Set `ADAPTER_PATH`
or `FINFLOW_TRAINING_DIR` when the Stage 4 adapter is stored elsewhere.

## Stage 5 frontend demo

The minimal receipt demo connects an image upload to the existing OCR → QLoRA
inference → parser pipeline. Install the project requirements, then start the
API from the repository root:

```bash
uvicorn backend.app.main:app --reload
```

Open <http://127.0.0.1:8000/demo>, choose a receipt image, and click **Extract
Receipt Data**. Set `ADAPTER_PATH` (or `FINFLOW_TRAINING_DIR`) if the adapter is
stored somewhere other than the default Stage 4 path.

## Stage 4 completion

Stage 4 QLoRA training and the 347-document Colab comparison are complete. The
verified adapter reached 88.83% macro field accuracy and 67.15% all-fields-correct
on the saved official test evaluation, versus 71.54% and 23.92% for the base
model. See [docs/stage4-results.md](docs/stage4-results.md) for provenance,
integrity qualifications, environment notes, and the model-free artifact
verifier. Raw predictions, adapters, checkpoints, and model files are not
committed.

## Stage 5A human review

Receipt ingestion is now review-first: extraction snapshots are validated and
held in `needs_review`, corrections are stored separately, and an expense is
created only after explicit approval. Run the local mock demonstration with
`FINFLOW_MOCK_EXTRACTION=1`; mock values are not AI inference. See
[docs/stage5a-human-review.md](docs/stage5a-human-review.md) for the lifecycle,
API endpoints, migration, and local-only security limitation.
# FinFlowML

Stage 5B adds authenticated, organization-scoped receipt review and accounting APIs. Read [docs/stage5b-security.md](docs/stage5b-security.md) for configuration, RBAC, migration safety, and local demonstration instructions.

Stage 5C adds durable asynchronous receipt jobs. See [docs/stage5c-async-processing.md](docs/stage5c-async-processing.md).

Stage 5D.1 adds audit events and job observability. See [docs/stage5d1-audit-observability.md](docs/stage5d1-audit-observability.md).

## Stage 6B private Docker staging

The CPU/mock Compose stack, explicit migrations, persistent Postgres/upload
volumes, and optional external-adapter GPU worker are documented in
[docs/stage6b-docker.md](docs/stage6b-docker.md). It binds the API to localhost
by default and never copies model weights, adapters, receipts, `.env` files, or
credentials into images.

## Stage 6E.1 SaaS frontend

The working Next.js frontend is in [`frontend/`](frontend/) and its local setup,
session model, API integration and validation commands are documented in
[`docs/stage6e1-frontend.md`](docs/stage6e1-frontend.md). It is intended for
local development against the existing FastAPI API and clearly labelled mock
worker; it is not a production deployment claim.

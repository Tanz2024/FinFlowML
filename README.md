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

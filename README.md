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

# Development setup

## Backend

```bash
uv venv .venv
uv pip install -r requirements.txt
```

Run the API locally (defaults to a local Postgres via `DATABASE_URL` in `.env`,
see `backend/app/core/config.py`):

```bash
.venv/bin/uvicorn backend.app.main:app --reload
```

Apply migrations:

```bash
cd backend && ../.venv/bin/alembic upgrade head
```

Create a new migration after changing a model in `backend/app/models/`:

```bash
cd backend && ../.venv/bin/alembic revision -m "describe the change"
```

Add the new model's import to `backend/app/database/base.py` so Alembic and
`Base.metadata.create_all` (used by tests) see it.

## Tests

```bash
.venv/bin/pytest backend/tests ml/tests
```

Backend tests use an in-memory SQLite database (`backend/tests/conftest.py`)
and don't require a running Postgres instance.

## Lint

```bash
.venv/bin/ruff check backend ml
```

## ML

Training, OCR, inference, and the parser are stable — see
`docs/backend-architecture.md` before changing them. `ml/inference/predict.py`
is the integration point the backend's demo route (`backend/app/demo.py`)
calls into.

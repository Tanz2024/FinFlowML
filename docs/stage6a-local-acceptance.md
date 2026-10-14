# Stage 6A local acceptance

These commands exercise the existing API, worker, and `/demo` interface in
mock mode. Mock values are labeled in the UI and are not Qwen inference.

## PostgreSQL and application

Start PostgreSQL using the local service for your machine, then configure
`.env` with a random `AUTH_SECRET` and local `DATABASE_URL`:

```bash
createdb finflowml  # if it does not already exist
cd backend
../.venv/bin/alembic upgrade head
cd ..
FINFLOW_MOCK_EXTRACTION=true .venv/bin/uvicorn backend.app.main:app --reload
```

In another terminal, start the worker:

```bash
FINFLOW_MOCK_EXTRACTION=true .venv/bin/python backend/worker.py
```

Open `http://127.0.0.1:8000/demo`, log in, upload an image, wait for the
worker, edit a field, save, then approve or reject explicitly.

## Playwright

Install the optional browser test dependencies once:

```bash
.venv/bin/pip install playwright
.venv/bin/python -m playwright install chromium
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8000 \
PLAYWRIGHT_EMAIL=test@example.com \
PLAYWRIGHT_PASSWORD=test-password-123 \
.venv/bin/pytest backend/tests/browser -q
```

The repository's normal test suite skips these tests when Playwright is not
installed. The complete upload/worker/approval scenario requires a seeded
PostgreSQL account and a receipt ID for review-state tests.

## Security notes

The API now emits baseline security headers including CSP, clickjacking and
MIME-sniffing protections. HTTPS termination, production secret management,
CORS policy, rate limiting, deployment isolation, and browser security review
remain required before staging or production exposure.

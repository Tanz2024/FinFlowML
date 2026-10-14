# Stage 6F acceptance

Acceptance runs are restricted to a disposable PostgreSQL database named
`finflowml_acceptance`. The runner refuses other database URLs.

```bash
createdb finflowml_acceptance
./scripts/run_acceptance.sh
```

Start the application in separate terminals after the preparation checks:

```bash
export DATABASE_URL='postgresql+psycopg://tanz@localhost:5432/finflowml_acceptance'
export FINFLOW_MOCK_EXTRACTION=1
export ENVIRONMENT=test
export AUTH_SECRET='local-acceptance-secret-change-me-32chars'
uvicorn backend.app.main:app --reload
FINFLOW_MOCK_EXTRACTION=1 python -m backend.worker
cd frontend && npm run dev
```

The repository currently has PostgreSQL integration tests but does not yet contain
a seeded Next.js Playwright fixture. Browser acceptance must not be reported as
passed until that fixture is added and Chromium is run against the three live
processes.

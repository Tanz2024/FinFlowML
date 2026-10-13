# Stage 5D.1: audit trails and job observability

Migration `0011_audit_events` adds tenant-scoped audit events. Events are written in the same SQLAlchemy transaction as the associated operation where practical: upload/job creation, extraction completion/failure, retry requests, corrections, approvals, rejections, and expense creation. Structured details deliberately exclude passwords, bearer tokens, OCR text, raw model output, and image data. Model ID, revision, adapter fingerprint, and job correlation IDs are retained for extraction provenance.

`GET /admin/audit-events` and `GET /admin/jobs` are limited to the authenticated organization and `manage_users` permission, with bounded pagination. Retry remains an authenticated reviewer operation and is audited. There is no delete or update API for events. This is append-only application behavior, not tamper-proof audit storage: a database administrator can still modify rows. Immutable retention, external/WORM storage, and database policy enforcement are future operational work.

Job logs are JSON-compatible and include job ID, organization ID, fence, retry count, terminal status, and extraction latency. In-process counters cover processing, completion, and failure events; they are intentionally lightweight and reset on worker restart. Queue waiting time and durable metrics export remain future work.

Run local verification:

```bash
DATABASE_URL='postgresql+psycopg://finflowml@localhost/finflowml_dev' \
  alembic -c backend/alembic.ini upgrade head
DATABASE_URL='postgresql+psycopg://finflowml@localhost/finflowml_test' \
  alembic -c backend/alembic.ini upgrade head
FINFLOW_POSTGRES_TEST_URL='postgresql+psycopg://finflowml@localhost/finflowml_test' \
  pytest -q
```

The API and worker remain separate processes. Stage 4 artifacts and benchmark reports are outside this audit/observability change.

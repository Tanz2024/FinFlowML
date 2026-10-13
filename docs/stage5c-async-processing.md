# Stage 5C: durable asynchronous document processing

Stage 5C changes receipt upload from synchronous extraction to a durable database-backed queue.

## Architecture

`POST /predict` requires authentication, a tenant-scoped `Idempotency-Key`, and a valid image. The payload is written under `UPLOAD_ROOT/<organization-id>/` before a database job is created, and the API returns HTTP 202 with `job_id` and `receipt_id`. No temporary upload path is handed to a worker.

Run the worker separately with:

```bash
FINFLOW_MOCK_EXTRACTION=true python -m backend.worker
```

The worker claims queued jobs transactionally, uses the receipt and organization IDs stored on the job, and persists successful extraction as raw model output followed by `needs_review`. It never creates an expense. Job states are `queued`, `processing`, `completed`, `retryable_failed`, and `terminal_failed`. Leases allow stale processing jobs to be reclaimed after a crash; retries use exponential backoff and a configurable limit.

Status and retry endpoints are tenant-scoped:

```text
GET  /jobs/{job_id}
POST /jobs/{job_id}/retry
```

Configure `UPLOAD_ROOT`, `MAX_UPLOAD_BYTES`, `EXTRACTION_MAX_RETRIES`, `EXTRACTION_LEASE_SECONDS`, `MODEL_ID`, `ADAPTER_PATH`, and `WORKER_VERSION`. Install Pillow for actual image decoding. `FINFLOW_MOCK_EXTRACTION=true` is deterministic local testing only and is labeled as mock; it is not AI inference. Real Qwen inference belongs in a long-lived GPU worker process so model weights are not reloaded per document.

SQLite is retained for unit tests. PostgreSQL is required for production queue concurrency and should be used for integration tests of row locking, leases, and concurrent idempotency races. The current local implementation is not a public deployment: object storage, malware scanning, distributed rate limits, worker observability, dead-letter operations, and database row-level security remain Stage 5D work.

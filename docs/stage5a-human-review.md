# Stage 5A: human review and safe receipt processing

Stage 5A changes receipt ingestion from automatic accounting to review-first
processing. `POST /receipts` stores the model/extraction snapshot and performs
deterministic validation, but it never creates an `Expense`.

## Lifecycle

```text
pending -> processing -> needs_review -> approved
                                      -> rejected
processing -> failed -> processing
```

Approval is the only receipt workflow transition that creates an expense.
Repeated approval returns the existing expense and does not create a duplicate.
The raw extraction is stored in `raw_extracted_data`; human edits are stored in
`corrected_data`. Original predictions are never overwritten.

## API

- `POST /receipts` — create and validate a receipt; returns `needs_review`.
- `GET /receipts/pending` — list pending/review receipts.
- `GET /receipts/{id}` — inspect raw, corrected, and validation data.
- `GET /receipts/{id}/status` — inspect effective values and expense status.
- `PATCH /receipts/{id}/corrections` — submit allowed field corrections.
- `POST /receipts/{id}/approve` — validate and transactionally create the expense.
- `POST /receipts/{id}/reject` — terminal rejection; no expense is created.

Validation requires a company, address, ISO date not in the future, positive
amount, and a three-letter alphabetic currency code. Valid JSON alone is not
considered valid financial extraction.

## Local demonstration

Install dependencies and start the API:

```bash
cp .env.example .env
cd backend && alembic upgrade head && cd ..
FINFLOW_MOCK_EXTRACTION=1 uvicorn backend.app.main:app --reload
```

Open <http://127.0.0.1:8000/demo>. Mock mode is visibly labeled in the page and
is not AI inference; it exists for Mac/local workflow demonstrations without a
CUDA GPU. Upload a file, review/edit the fields, then approve or reject it.

## Migration and security notes

Migration `0005_receipt_review_workflow` adds nullable JSON columns and maps
legacy `extracted`/`processed` statuses to `needs_review`. It does not alter
Stage 4 artifacts, model files, benchmark reports, or saved adapters.

Review endpoints are local-only prototype functionality. The application has
no authentication, authorization, or tenant isolation. Do not expose this API
to untrusted users or use it with shared financial data until Stage 5B adds
those controls.

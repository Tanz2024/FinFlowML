# FinFlowML product roadmap

## Current state: Stage 5

Receipt images flow through PaddleOCR, Qwen3-4B + LoRA extraction, structured
parser validation, and a FastAPI demo. ML remains separate from persistence.

## Phase 2 — Expense Intelligence (complete)

The backend foundation adds `receipts`, `expenses`, and `expense_categories`. A
receipt retains OCR text and the structured extraction snapshot; an expense is
the normalized, categorizable financial record. Receipt ingestion now
automatically runs `services/expense_pipeline.py`, which matches a merchant to
a category (`services/category_matcher.py`, falling back to "Uncategorized"),
normalizes currency and amount (`services/currency.py`), and creates the
expense. APIs: receipt ingestion, expense creation, category listing, and
spending summaries by category and month. Next: category CRUD, review
workflows, and richer analytics by merchant and currency.

## Phase 3 — Invoice + Accounting (complete)

`Invoice`, `InvoiceItem`, and `Payment` models support business documents with
supplier/customer metadata, line items, and a `PaymentStatus` enum.
`services/accounting.py` derives revenue, expenses, and profit from existing
payment and expense records. APIs: `POST /invoices` (with line items),
`GET /accounting/summary`, `GET /accounting/monthly-report`.

## Phase 4 — Revenue Forecasting (foundation complete)

`RevenueSnapshot` stores historical financial time-series points, and
`services/forecasting.py` defines the `ForecastingProvider` interface with a
deterministic `NaiveAverageForecastingProvider` baseline. Real providers
(Prophet, XGBoost, transformer-based models) implement the same interface.
Not yet built: a job to populate snapshots and a production-grade provider.

## Phase 5 — AI Finance Assistant (foundation complete)

`services/financial_query.py` defines a `FinancialRetriever` interface and
`build_context()`, which assembles a typed, source-cited `FinancialContext`
from existing accounting/expense data — exposed read-only via
`GET /assistant/context`. Retrievers never expose raw table access; a future
LLM assistant consumes only the typed context. Not yet built: the LLM-backed
answer generation itself.

See `docs/backend-architecture.md` for ownership boundaries and contributor
issues.

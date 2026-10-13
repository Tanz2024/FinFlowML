# Backend architecture notes

- `ml/` owns OCR, prompts, model loading, extraction, and parser validation.
- `backend/app/models` owns SQLAlchemy persistence.
- `backend/app/schemas` owns public request/response contracts.
- `backend/app/services` owns workflows and accounting calculations.
- `backend/app/api` contains thin HTTP adapters.
- Alembic migrations are the production schema source of truth.

Phase 2 exposes thin API adapters: `/receipts` persists extraction snapshots and
runs `services/expense_pipeline.py`, which creates a normalized `Expense` with
merchant-based category matching (`services/category_matcher.py`) and currency
normalization (`services/currency.py`); `/expenses/summary` provides read-only
category and monthly aggregation. As filtering and authorization grow, move
query logic into services/repositories.

The Stage 5 demo is an integration boundary. Ingestion calls the existing model
pipeline, persists the output as a receipt, and the receipt route triggers the
expense pipeline automatically. Raw OCR and extracted JSON are retained for
review and reprocessing.

## Phase 3 — invoices and accounting

`Invoice`/`InvoiceItem`/`Payment` model business documents; `Invoice.status` is
a free-text column backed by the `PaymentStatus` enum for validation.
`services/invoicing.py` persists an invoice with its line items in one
transaction. `services/accounting.py` derives revenue (paid invoice amounts),
expenses, and profit — it is pure read-side aggregation, not a source of truth.
`GET /accounting/summary` and `GET /accounting/monthly-report` expose it.

## Phase 4 — forecasting foundation

`RevenueSnapshot` is a minimal time-series table for future forecasting input;
nothing writes to it yet. `services/forecasting.py` defines the
`ForecastingProvider` interface plus a deterministic `NaiveAverageForecastingProvider`
placeholder — real providers (Prophet, XGBoost, transformer-based) should
implement the same interface rather than changing call sites.

## Phase 5 — AI finance assistant foundation

`services/financial_query.py` defines a `FinancialRetriever` interface and a
`build_context()` function that assembles a typed, source-cited
`FinancialContext` from existing accounting/expense data. `GET
/assistant/context?q=...` exposes it for inspection. No LLM is wired in yet —
retrievers never expose raw table access to a future assistant, only typed,
attributed facts.

## Suggested contributor issues

1. Add idempotent receipt ingestion and review services.
2. Add expense-category CRUD and richer merchant-matching rules (fuzzy match,
   user-defined rules).
3. Add analytics queries with date, currency, merchant, and category filters.
4. Add invoice PDF/email extraction into the `InvoiceCreate` schema.
5. Add a job that populates `RevenueSnapshot` from `Payment` history, and a
   real `ForecastingProvider` (Prophet or XGBoost) implementation.
6. Add more `FinancialRetriever` implementations (trend/anomaly detection for
   "why did expenses increase?") and wire an LLM behind `build_context()`.
7. Add API contract fixtures and OpenAPI examples for frontend clients.
8. Add authorization/tenant boundaries before multi-user access.
9. Add PostgreSQL migration integration tests.

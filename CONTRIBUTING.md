# Contributing to FinFlowML

FinFlowML has three loosely-coupled ownership areas. Pick issues that match
where you want to contribute; cross-cutting changes should still respect the
boundaries below.

## Ownership boundaries

- **AI/ML** (`ml/`): OCR (`ml/ocr`), model loading (`ml/modeling`), training
  (`ml/training`), extraction/parsing (`ml/extraction`), inference
  (`ml/inference`), and evaluation (`ml/evaluation`). Changes here should not
  require backend changes; `ml/inference/predict.py` is the seam the backend
  calls through.
- **Backend** (`backend/`): APIs (`backend/app/api`), database models
  (`backend/app/models`), business logic (`backend/app/services`), and
  request/response contracts (`backend/app/schemas`). Route handlers should
  stay thin — put logic in a service module, not in `routes.py`.
- **Frontend**: dashboard, mobile apps, and UI. Not yet present in this repo —
  see `docs/backend-architecture.md` for the API surface to build against.

See `docs/backend-architecture.md` for the current architecture and a list of
suggested first issues per phase.

## Workflow

1. Fork/branch, make a focused change (one feature or fix per PR).
2. Add tests for new backend logic (`backend/tests/`) or ML logic
   (`ml/tests/`) — see `DEVELOPMENT.md` for how to run them.
3. Run `ruff check` and `pytest` before opening a PR; both must pass.
4. Do not modify existing training, OCR, inference, parser, or model-loader
   code without discussion — these are stable, validated components.
5. Keep new backend functionality behind a service module rather than inline
   in a route, so it stays independently testable.

## Code style

- Python 3.11+, type hints on new public functions.
- No speculative abstractions — implement what the issue asks for.
- Comments only where the *why* isn't obvious from the code.

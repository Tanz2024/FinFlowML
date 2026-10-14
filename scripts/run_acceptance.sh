#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_URL="${DATABASE_URL:-postgresql+psycopg://tanz@localhost:5432/finflowml_acceptance}"
python3 - "$DB_URL" <<'PY'
import sys
from urllib.parse import urlparse

raw = sys.argv[1]
parsed = urlparse(raw.replace("postgresql+psycopg://", "postgresql://", 1))
if parsed.scheme not in {"postgresql", "postgres"}:
    raise SystemExit("Refusing acceptance run: DATABASE_URL must use PostgreSQL")
if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("Refusing acceptance run: database host must be local")
if parsed.path.lstrip("/") != "finflowml_acceptance":
    raise SystemExit("Refusing acceptance run: database name must be finflowml_acceptance")
if parsed.query or parsed.fragment:
    raise SystemExit("Refusing acceptance run: database URL must not contain query or fragment parameters")
PY
export DATABASE_URL="$DB_URL"
export FINFLOW_POSTGRES_TEST_URL="$DB_URL"
export FINFLOW_MOCK_EXTRACTION=1
export ENVIRONMENT=test
export AUTH_SECRET="${AUTH_SECRET:-local-acceptance-secret-change-me-32chars}"

cd "$ROOT/backend"
"$ROOT/.venv/bin/alembic" upgrade head
cd "$ROOT"
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" scripts/seed_acceptance.py
"$ROOT/.venv/bin/pytest" -q backend/tests/test_postgres_integration.py
"$ROOT/.venv/bin/ruff" check .
cd "$ROOT/frontend"
npm ci
npm run typecheck
npm run lint
npm test
npm run build
if [[ "${RUN_BROWSER:-0}" == "1" ]]; then
  npx playwright install chromium
  npx playwright test
fi
echo "Acceptance preparation checks passed. Start API, worker and frontend before browser tests."

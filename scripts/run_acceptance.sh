#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_URL="${DATABASE_URL:-postgresql+psycopg://tanz@localhost:5432/finflowml_acceptance}"
case "$DB_URL" in
  *finflowml_acceptance) ;;
  *) echo "Refusing acceptance run: DATABASE_URL must target finflowml_acceptance" >&2; exit 2 ;;
esac
export DATABASE_URL="$DB_URL"
export FINFLOW_POSTGRES_TEST_URL="$DB_URL"
export FINFLOW_MOCK_EXTRACTION=1
export ENVIRONMENT=test
export AUTH_SECRET="${AUTH_SECRET:-local-acceptance-secret-change-me-32chars}"

cd "$ROOT/backend"
"$ROOT/.venv/bin/alembic" upgrade head
cd "$ROOT"
"$ROOT/.venv/bin/pytest" -q backend/tests/test_postgres_integration.py
"$ROOT/.venv/bin/ruff" check .
cd "$ROOT/frontend"
npm ci
npm run typecheck
npm run lint
npm test
npm run build
echo "Acceptance preparation checks passed. Start API, worker and frontend before browser tests."

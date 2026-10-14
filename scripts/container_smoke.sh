#!/usr/bin/env bash
set -euo pipefail
base_url="${BASE_URL:-http://127.0.0.1:8000}"
curl --fail --silent "${base_url}/health" | grep -q '"status":"ok"'
echo "container health: ok"

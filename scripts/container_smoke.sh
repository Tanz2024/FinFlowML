#!/usr/bin/env bash
set -euo pipefail
base_url="${BASE_URL:-http://127.0.0.1:8000}"
curl --fail --silent "${base_url}/health" | grep -q '"status":"ok"'
echo "container health: ok"
if [[ -z "${SMOKE_EMAIL:-}" || -z "${SMOKE_PASSWORD:-}" || -z "${SMOKE_IMAGE:-}" ]]; then
  echo "container health check completed; AI workflow was NOT run (set SMOKE_EMAIL, SMOKE_PASSWORD, and SMOKE_IMAGE)"
  exit 0
fi
if [[ "${FINFLOW_MOCK_EXTRACTION:-false}" == "true" || "${FINFLOW_MOCK_EXTRACTION:-false}" == "1" ]]; then
  echo "refusing to label mock extraction as a real GPU workflow" >&2
  exit 2
fi
BASE_URL="$base_url" python3 - <<'PY'
import os
import time
import uuid
from pathlib import Path
import requests
base = os.environ["BASE_URL"]
s = requests.Session()
login = s.post(base + "/auth/login", json={"email": os.environ["SMOKE_EMAIL"], "password": os.environ["SMOKE_PASSWORD"]})
login.raise_for_status()
s.headers["Authorization"] = "Bearer " + login.json()["access_token"]
with Path(os.environ["SMOKE_IMAGE"]).open("rb") as image:
    uploaded = s.post(base + "/predict", files={"receipt": ("smoke.jpg", image, "image/jpeg")}, headers={"Idempotency-Key": str(uuid.uuid4())})
uploaded.raise_for_status()
job = uploaded.json()["job_id"]
receipt = uploaded.json()["receipt_id"]
timeout = int(os.environ.get("SMOKE_TIMEOUT_SECONDS", "900"))
deadline = time.monotonic() + timeout
retried = False
while time.monotonic() < deadline:
    status = s.get(base + "/jobs/" + job)
    status.raise_for_status()
    state = status.json()["state"]
    if state == "completed":
        break
    if state in {"terminal_failed", "retryable_failed"}:
        if os.environ.get("SMOKE_RETRY_FAILED", "false").lower() == "true" and not retried:
            retry = s.post(base + "/jobs/" + job + "/retry")
            retry.raise_for_status()
            retried = True
            continue
        raise SystemExit(f"worker failed: {status.text}")
    time.sleep(1)
else:
    raise SystemExit(f"worker did not complete within {timeout} seconds")
expected_model = os.environ.get("MODEL_ID", "Qwen/Qwen3-4B-Instruct-2507")
expected_revision = os.environ.get("MODEL_REVISION", "cdbee75f17c01a7cc42f958dc650907174af0554")
if status.json().get("model_id") != expected_model or status.json().get("model_revision") != expected_revision:
    raise SystemExit("worker did not report the configured real model and revision")
if not status.json().get("adapter_fingerprint"):
    raise SystemExit("worker did not report an adapter fingerprint")
review = s.get(base + f"/receipts/{receipt}/review")
review.raise_for_status()
field = review.json()["fields"]["company"]["effective_value"]
correction = s.patch(base + f"/receipts/{receipt}/corrections", json={"corrections": {"company": field + " reviewed"}})
correction.raise_for_status()
before = len(s.get(base + "/expenses").json())
approved = s.post(base + f"/receipts/{receipt}/approve")
approved.raise_for_status()
after = len(s.get(base + "/expenses").json())
if after != before + 1:
    raise SystemExit(f"approval created {after - before} expenses; expected exactly one")
repeat = s.post(base + f"/receipts/{receipt}/approve")
if repeat.status_code not in {200, 409}:
    repeat.raise_for_status()
if len(s.get(base + "/expenses").json()) != after:
    raise SystemExit("repeated approval created a duplicate expense")
print("workflow smoke completed: upload, non-mock worker, review, correction, approval, idempotency")
PY

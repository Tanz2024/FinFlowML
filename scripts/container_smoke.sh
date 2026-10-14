#!/usr/bin/env bash
set -euo pipefail
base_url="${BASE_URL:-http://127.0.0.1:8000}"
curl --fail --silent "${base_url}/health" | grep -q '"status":"ok"'
echo "container health: ok"
if [[ -z "${SMOKE_EMAIL:-}" || -z "${SMOKE_PASSWORD:-}" || -z "${SMOKE_IMAGE:-}" ]]; then
  echo "health-only smoke passed; set SMOKE_EMAIL, SMOKE_PASSWORD, and SMOKE_IMAGE for workflow smoke"
  exit 0
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
for _ in range(60):
    status = s.get(base + "/jobs/" + job)
    status.raise_for_status()
    state = status.json()["state"]
    if state == "completed":
        break
    if state in {"terminal_failed", "retryable_failed"}:
        raise SystemExit(f"worker failed: {status.text}")
    time.sleep(1)
else:
    raise SystemExit("worker did not complete within 60 seconds")
review = s.get(base + f"/receipts/{receipt}/review")
review.raise_for_status()
field = review.json()["fields"]["company"]["effective_value"]
correction = s.patch(base + f"/receipts/{receipt}/corrections", json={"corrections": {"company": field + " reviewed"}})
correction.raise_for_status()
approved = s.post(base + f"/receipts/{receipt}/approve")
approved.raise_for_status()
print("workflow smoke passed: upload, worker, review, correction, approval")
PY

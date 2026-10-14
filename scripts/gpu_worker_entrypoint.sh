#!/usr/bin/env bash
set -euo pipefail

python /app/scripts/validate_gpu_runtime.py
exec "$@"

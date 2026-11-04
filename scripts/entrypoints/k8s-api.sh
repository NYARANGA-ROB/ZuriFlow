#!/usr/bin/env bash
# Kubernetes API entrypoint — single uvicorn process per pod.
# Scale horizontally via Deployment replicas / HPA (not in-process workers).
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$(dirname "$(dirname "${BASH_SOURCE[0]}")")")" && pwd)"
cd "$BASE_DIR"

export PYTHONPATH="${PYTHONPATH:-/app}"
export LOG_TO_FILE="${LOG_TO_FILE:-false}"

exec uvicorn api.app:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 1 \
  --proxy-headers \
  --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"

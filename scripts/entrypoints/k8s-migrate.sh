#!/usr/bin/env bash
# One-shot database migration job for Kubernetes.
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$(dirname "$(dirname "${BASH_SOURCE[0]}")")")" && pwd)"
cd "$BASE_DIR"

export PYTHONPATH="${PYTHONPATH:-/app}"

echo "Running Alembic migrations..."
alembic -c "$BASE_DIR/api/alembic.ini" upgrade head
echo "Migrations complete."

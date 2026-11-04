#!/usr/bin/env bash
# Run realtime voice WebSocket load test against a local or remote server.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -d venv ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

pip install -q -r scripts/load_test/requirements.txt

exec python scripts/run_realtime_voice_load_test.py "$@"

#!/usr/bin/env bash
# Run workflow reliability pytest suite (no live server required).
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi
if [[ -f api/.env.test ]]; then
  set -a
  # shellcheck disable=SC1091
  source api/.env.test
  set +a
elif [[ -f api/.env.test.example ]]; then
  set -a
  # shellcheck disable=SC1091
  source api/.env.test.example
  set +a
fi
python -m pytest api/tests/load/ -m reliability -v "$@"

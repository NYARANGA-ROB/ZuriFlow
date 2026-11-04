#!/usr/bin/env bash
# Kubernetes background worker entrypoint — singleton orchestrators + ARQ pool.
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$(dirname "$(dirname "${BASH_SOURCE[0]}")")")" && pwd)"
cd "$BASE_DIR"

export PYTHONPATH="${PYTHONPATH:-/app}"
export LOG_TO_FILE="${LOG_TO_FILE:-false}"

ARQ_WORKERS="${ARQ_WORKERS:-2}"
ENABLE_ARI_MANAGER="${ENABLE_ARI_MANAGER:-true}"
ENABLE_CAMPAIGN_ORCHESTRATOR="${ENABLE_CAMPAIGN_ORCHESTRATOR:-true}"

pids=()

shutdown() {
  echo "Worker shutdown: sending SIGTERM to children..."
  for pid in "${pids[@]}"; do
    kill -TERM "$pid" 2>/dev/null || true
  done
  wait || true
  exit 0
}

trap shutdown TERM INT

start() {
  local name=$1
  shift
  echo "→ Starting $name"
  "$@" &
  pids+=($!)
}

if [[ "$ENABLE_ARI_MANAGER" == "true" ]]; then
  start ari_manager python -m api.services.telephony.ari_manager
fi

if [[ "$ENABLE_CAMPAIGN_ORCHESTRATOR" == "true" ]]; then
  start campaign_orchestrator python -m api.services.campaign.campaign_orchestrator
fi

for ((i=1; i<=ARQ_WORKERS; i++)); do
  start "arq$i" python -m arq api.tasks.arq.WorkerSettings --custom-log-dict api.tasks.arq.LOG_CONFIG
done

wait -n
echo "A worker process exited; tearing down pod."
shutdown

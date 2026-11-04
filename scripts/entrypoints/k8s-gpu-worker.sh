#!/usr/bin/env bash
# GPU worker entrypoint — ARQ workers for GPU-bound voice inference tasks.
# Requires nvidia.com/gpu resource limits on the pod and CUDA-capable nodes.
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$(dirname "$(dirname "${BASH_SOURCE[0]}")")")" && pwd)"
cd "$BASE_DIR"

export PYTHONPATH="${PYTHONPATH:-/app}"
export LOG_TO_FILE="${LOG_TO_FILE:-false}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

ARQ_WORKERS="${ARQ_WORKERS:-1}"
GPU_QUEUE_NAME="${GPU_QUEUE_NAME:-gpu_voice}"

echo "Starting GPU worker (queue=${GPU_QUEUE_NAME}, workers=${ARQ_WORKERS})"

if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi -L || echo "Warning: nvidia-smi unavailable"
else
  echo "Warning: running without nvidia-smi — ensure GPU drivers are mounted"
fi

pids=()
shutdown() {
  for pid in "${pids[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
  wait || true
  exit 0
}
trap shutdown TERM INT

for ((i=1; i<=ARQ_WORKERS; i++)); do
  echo "→ Starting gpu-arq$i"
  ARQ_QUEUE_NAME="$GPU_QUEUE_NAME" \
    python -m arq api.tasks.arq.WorkerSettings --custom-log-dict api.tasks.arq.LOG_CONFIG &
  pids+=($!)
done

wait -n
shutdown

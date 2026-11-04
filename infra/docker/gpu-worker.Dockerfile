# syntax=docker/dockerfile:1
# GPU worker for optional on-cluster STT / accent inference workloads.
# Build on a CUDA-capable host:
#   docker build -f infra/docker/gpu-worker.Dockerfile -t dograh-gpu-worker:k8s .
#
# Requires NVIDIA Container Toolkit on nodes and `nvidia.com/gpu` limits in Helm.

ARG API_IMAGE=dograh-api:k8s
FROM ${API_IMAGE} AS base

USER root
# Optional GPU Python stack — install only when building gpu-worker target.
RUN --mount=type=bind,source=api/requirements.kenyan-accent.txt,target=/tmp/gpu-req.txt \
    if [ -f /tmp/gpu-req.txt ]; then \
      /opt/venv/bin/pip install --no-cache-dir -r /tmp/gpu-req.txt || true; \
    fi
RUN chmod +x /app/scripts/entrypoints/k8s-gpu-worker.sh
USER dograh

ENV ARQ_WORKERS=1 GPU_QUEUE_NAME=gpu_voice NVIDIA_VISIBLE_DEVICES=all
HEALTHCHECK NONE
CMD ["./scripts/entrypoints/k8s-gpu-worker.sh"]

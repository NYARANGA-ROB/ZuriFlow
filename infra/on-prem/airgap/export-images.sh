#!/usr/bin/env bash
# Export Dograh and dependency images for air-gapped transfer.
set -euo pipefail

OUTPUT="${1:-dograh-images.tar}"
REGISTRY="${REGISTRY:-ghcr.io}"

IMAGES=(
  "${REGISTRY}/dograh/dograh-api:latest"
  "${REGISTRY}/dograh/dograh-worker:latest"
  "${REGISTRY}/dograh/dograh-ui:latest"
  "${REGISTRY}/dograh/dograh-gpu-worker:latest"
  "pgvector/pgvector:pg17"
  "redis:7-alpine"
  "minio/minio:latest"
  "vllm/vllm-openai:latest"
  "otel/opentelemetry-collector-contrib:0.109.0"
  "jaegertracing/all-in-one:1.57"
  "grafana/loki:3.0.0"
  "grafana/grafana:11.1.0"
  "prom/prometheus:v2.53.0"
)

echo "Pulling ${#IMAGES[@]} images..."
for img in "${IMAGES[@]}"; do
  docker pull "$img"
done

echo "Saving to ${OUTPUT}"
docker save "${IMAGES[@]}" -o "$OUTPUT"
echo "Done. Transfer ${OUTPUT} to the air-gapped environment."

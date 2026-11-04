# syntax=docker/dockerfile:1
# Background worker image — ARQ + telephony/campaign orchestrators.
# Build: docker build -f infra/docker/worker.Dockerfile -t dograh-worker:k8s .

ARG API_IMAGE=dograh-api:k8s
FROM ${API_IMAGE}

USER root
RUN chmod +x /app/scripts/entrypoints/k8s-worker.sh /app/scripts/entrypoints/k8s-migrate.sh
USER dograh

ENV ARQ_WORKERS=2
HEALTHCHECK NONE
CMD ["./scripts/entrypoints/k8s-worker.sh"]

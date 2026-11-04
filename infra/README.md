# Dograh Production Infrastructure

Kubernetes deployment assets for the Dograh AI voice platform.

## Layout

```
infra/
├── docker/                 # Production Dockerfiles (API, worker, GPU, nginx)
├── helm/dograh/            # Helm chart (recommended)
├── kubernetes/base/        # Raw Kustomize manifests
└── observability/          # Prometheus/Grafana/OTel stack
scripts/entrypoints/        # K8s process entrypoints (api, worker, gpu, migrate)
```

## Quick start (Helm)

### Prerequisites

- Kubernetes 1.28+
- NGINX Ingress Controller (WebSocket support)
- cert-manager (optional, for TLS)
- Prometheus Operator (optional, for ServiceMonitor)
- KEDA (optional, for Redis queue autoscaling)
- NVIDIA device plugin (optional, for GPU workers)

### Install

```bash
# 1. Create secrets (production — use External Secrets Operator in real deployments)
kubectl create namespace dograh
kubectl -n dograh create secret generic dograh-production-secrets \
  --from-literal=OSS_JWT_SECRET='...' \
  --from-literal=POSTGRES_PASSWORD='...' \
  --from-literal=REDIS_PASSWORD='...' \
  --from-literal=DATABASE_URL='postgresql+asyncpg://...' \
  --from-literal=REDIS_URL='redis://:...@...:6379'

# 2. Deploy
helm upgrade --install dograh ./infra/helm/dograh \
  --namespace dograh \
  -f infra/helm/dograh/values-production.yaml \
  --set ingress.hosts[0].host=voice.yourcompany.com \
  --set secrets.create=false \
  --set secrets.existingSecret=dograh-production-secrets \
  --set images.api.tag=1.0.0 \
  --set images.worker.tag=1.0.0 \
  --set images.ui.tag=1.0.0
```

### Kustomize (without Helm)

```bash
cp infra/kubernetes/base/secret.example.yaml infra/kubernetes/base/secret.yaml
# edit secret.yaml
kubectl apply -k infra/kubernetes/base/
```

## Architecture

| Component | K8s resource | Notes |
|-----------|--------------|-------|
| API + WebSockets | `Deployment` + HPA | 1 uvicorn/pod; scale replicas for voice traffic |
| Background jobs | `Deployment` + HPA/KEDA | ARQ + campaign/ARI orchestrators |
| GPU inference | `Deployment` (optional) | `nvidia.com/gpu` limits |
| UI | `Deployment` + HPA | Next.js standalone |
| Postgres | `StatefulSet` or external | pgvector/pg17 |
| Redis | `StatefulSet` or external | ARQ queue + session state |
| Ingress | `Ingress` | 3600s timeouts for WebSockets |

## WebSocket routes

The Ingress is configured for long-lived connections used by:

- `/api/v1/telephony/ws/*` — telephony media streams
- `/api/v1/ws/signaling/*` — WebRTC signaling
- `/api/v1/realtime-audio/ws` — PCM audio
- `/api/v1/realtime-voice/ws` — STT/LLM/TTS pipeline
- `/api/v1/agent-stream/*` — agent streaming

## Docker images

```bash
# API (single uvicorn process)
docker build -f infra/docker/api.Dockerfile -t dograh-api:k8s .

# Worker (depends on API image)
docker build -f infra/docker/api.Dockerfile -t dograh-api:k8s .
docker build -f infra/docker/worker.Dockerfile --build-arg API_IMAGE=dograh-api:k8s -t dograh-worker:k8s .

# GPU worker (optional)
docker build -f infra/docker/gpu-worker.Dockerfile --build-arg API_IMAGE=dograh-api:k8s -t dograh-gpu-worker:k8s .
```

The root `api/Dockerfile` remains the Compose/OSS monolith image. K8s deployments override the command to use `scripts/entrypoints/k8s-*.sh`.

## Autoscaling

| Target | Mechanism | Trigger |
|--------|-----------|---------|
| API | HPA | CPU 70%, memory 80% |
| Worker | HPA | CPU 75% |
| Worker | KEDA (optional) | Redis ARQ queue depth |
| UI | HPA | CPU 70% |
| GPU worker | Manual / future KEDA | GPU utilization |

## Observability

```bash
# Prometheus + Grafana
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f infra/observability/kube-prometheus-stack-values.yaml

kubectl apply -f infra/observability/grafana/dashboard-configmap.yaml
kubectl apply -f infra/observability/otel-collector.yaml
```

Metrics scrape endpoint: `GET /api/v1/realtime-observability/metrics`

## Enterprise on-prem

Air-gapped Kubernetes deployment with local GPU inference, tenant network policies, and in-cluster observability.

| Asset | Path |
|-------|------|
| Architecture | `infra/on-prem/ARCHITECTURE.md` |
| Quick start | `infra/on-prem/README.md` |
| Helm values | `infra/helm/dograh/values-on-prem.yaml` |
| Kustomize overlay | `infra/kubernetes/overlays/on-prem/` |
| GPU inference | `infra/on-prem/inference/` |
| Secrets (Vault/Sealed) | `infra/on-prem/secrets/` |
| Observability stack | `infra/on-prem/observability/` |
| Air-gap image bundle | `infra/on-prem/airgap/` |

Inference routing API: `GET /api/v1/realtime-observability/inference-routing`

```bash
helm upgrade --install dograh ./infra/helm/dograh \
  -f infra/helm/dograh/values-on-prem.yaml \
  --set global.imageRegistry=registry.internal:5000
```

## CI/CD

| Workflow | Purpose |
|----------|---------|
| `.github/workflows/docker-image.yml` | Multi-arch API + UI images on release |
| `.github/workflows/k8s-build.yml` | Validate K8s Dockerfiles + Helm lint |
| `.github/workflows/k8s-deploy.yml` | `helm upgrade` on release (requires `KUBE_CONFIG` secret) |

## Production checklist

- [ ] Use managed Postgres (RDS/Cloud SQL) — set `postgresql.external.enabled=true`
- [ ] Use managed Redis (ElastiCache/Memorystore) — set `redis.external.enabled=true`
- [ ] Configure TURN server for WebRTC (`TURN_HOST`, `TURN_SECRET`)
- [ ] Set strong `OSS_JWT_SECRET` and rotate API keys
- [ ] Enable PodDisruptionBudgets and cluster autoscaling
- [ ] Configure Sentry/Langfuse via `extraEnv`
- [ ] Load test WebSocket paths before go-live

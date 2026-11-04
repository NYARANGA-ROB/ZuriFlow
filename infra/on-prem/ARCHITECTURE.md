# Dograh Enterprise On-Prem Deployment Architecture

Air-gapped, Kubernetes-native deployment for regulated environments. All inference, storage, and observability run inside the customer network with no mandatory outbound internet access.

## Design goals

| Requirement | Implementation |
|-------------|----------------|
| Offline deployment | Private container registry, bundled images, no external Helm repos at install time |
| Kubernetes | Helm chart + Kustomize overlay (`infra/kubernetes/overlays/on-prem`) |
| Local GPU inference | Dedicated `dograh-inference` namespace (vLLM, Whisper, TTS) |
| Tenant isolation | App RBAC + NetworkPolicies + optional per-tenant namespaces |
| Private networking | Internal ingress, deny-by-default policies, cluster DNS only |
| Observability | Prometheus, Loki, Grafana, Jaeger, OTEL Collector (all in-cluster) |

## Topology

```
┌──────────────────────── Customer private network / VLAN ────────────────────────┐
│                                                                                 │
│  ┌────────────────────── dograh (application) ──────────────────────────────┐ │
│  │  Ingress (internal) ──▶ API / UI / WebSocket paths                        │ │
│  │  API + Worker + GPU-worker (ARQ)                                          │ │
│  │  PostgreSQL (StatefulSet)   Redis (StatefulSet)   MinIO (optional)        │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│           │ allowed egress (NetworkPolicy)                                      │
│           ▼                                                                     │
│  ┌────────────────────── dograh-inference (GPU) ─────────────────────────────┐ │
│  │  vLLM (LLM)   Faster-Whisper (STT)   Piper/Coqui (TTS)                    │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌────────────────────── dograh-observability ───────────────────────────────┐ │
│  │  OTEL Collector ──▶ Prometheus / Loki / Jaeger ──▶ Grafana                │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌────────────────────── dograh-secrets (optional) ────────────────────────────┐ │
│  │  Vault / Sealed Secrets / External Secrets Operator                       │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  Private registry (registry.internal:5000) — no pull from public internet       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Traffic flows

### Voice call (WebRTC / telephony)

1. Client connects to **internal ingress** (`voice.corp.internal`).
2. **API** handles signaling WebSockets (`/api/v1/ws/signaling`, `/api/v1/telephony/ws`).
3. **coturn** (optional, same VLAN) provides TURN for NAT traversal — deploy via Compose profile or separate Helm release.
4. **STT/LLM/TTS** calls route to cluster-local inference services (see `LOCAL_INFERENCE_ROUTES`).
5. **Worker** processes completion jobs (recordings, QA, billing) via ARQ/Redis.
6. Artifacts land in **MinIO** or customer S3-compatible store.

### Inference routing

Dograh API/worker pods read `LOCAL_INFERENCE_ROUTES` (JSON) from ConfigMap. Default on-prem endpoints:

| Service | In-cluster DNS | Provider in UI |
|---------|----------------|----------------|
| LLM | `http://dograh-vllm.dograh-inference.svc:8000/v1` | Speaches / OpenAI-compatible |
| STT | `http://dograh-whisper.dograh-inference.svc:9000` | Speaches |
| TTS | `http://dograh-tts.dograh-inference.svc:5000` | Speaches |

Configure org-level AI model settings to use these `base_url` values, or set deployment-wide defaults via `LOCAL_INFERENCE_ROUTES`.

### Tenant isolation

**Layer 1 — Application (always on)**  
Organization-scoped RBAC, row-level DB isolation, per-org configuration and API keys.

**Layer 2 — Network (recommended)**  
`NetworkPolicy` resources restrict:
- Ingress to API only from ingress controller and monitoring
- Egress from API/worker to Postgres, Redis, MinIO, and inference namespace only
- Inference pods accept traffic only from `dograh` namespace

**Layer 3 — Dedicated namespace (enterprise option)**  
Large tenants get `dograh-tenant-{id}` namespaces with ResourceQuota and separate Postgres schema or database. See `infra/on-prem/tenant/namespace-template.yaml`.

## Offline / air-gap install

1. On a connected bastion, run `infra/on-prem/airgap/export-images.sh` to save images to a tarball.
2. Transfer tarball to the air-gapped environment.
3. Load into `registry.internal` via `infra/on-prem/airgap/load-images.sh`.
4. Install from local Helm chart (no `helm repo add`):
   ```bash
   helm upgrade --install dograh ./infra/helm/dograh \
     -f infra/helm/dograh/values-on-prem.yaml \
     --set global.imageRegistry=registry.internal:5000
   ```

## Secrets

Production on-prem should **not** commit secrets to Git. Supported patterns (pick one):

| Pattern | Use when |
|---------|----------|
| **External Secrets Operator + Vault** | Enterprise PKI, rotation, audit |
| **Sealed Secrets** | GitOps with encrypted secrets in repo |
| **Pre-created K8s Secret** | Simple installs, manual rotation |

Manifests: `infra/on-prem/secrets/`

## Observability

All components stay in-cluster:

- **Metrics**: API `/api/v1/realtime-observability/metrics` → Prometheus ServiceMonitor
- **Logs**: Promtail → Loki → Grafana
- **Traces**: OTEL SDK → OTEL Collector → Jaeger
- **Dashboards**: `infra/on-prem/observability/grafana-dashboards/`

Set `ENABLE_TELEMETRY=true` and `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.dograh-observability.svc:4317` on API/worker pods.

## Sizing (starting point)

| Component | CPU | Memory | GPU | Replicas |
|-----------|-----|--------|-----|----------|
| API | 1–2 | 2–4 Gi | — | 2+ |
| Worker | 0.5–1 | 1–2 Gi | — | 2+ |
| PostgreSQL | 1–2 | 4–8 Gi | — | 1 (HA: Patroni) |
| Redis | 0.25 | 512 Mi–1 Gi | — | 1 |
| vLLM (7B) | 4 | 16 Gi | 1× A10/L4 | 1–2 |
| Whisper large | 2 | 8 Gi | 1 (optional) | 1 |

## Upgrade path

1. Run DB migrations (`migration` Helm hook / Job).
2. Rolling update API → worker → UI.
3. Roll inference models independently (vLLM image tag / model PVC).

## Related assets

- Helm values: `infra/helm/dograh/values-on-prem.yaml`
- Kustomize: `infra/kubernetes/overlays/on-prem/`
- Inference manifests: `infra/on-prem/inference/`
- Network policies: `infra/on-prem/tenant/network-policies.yaml`
- Observability: `infra/on-prem/observability/`

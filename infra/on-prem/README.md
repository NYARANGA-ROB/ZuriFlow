# On-Prem Quick Start

Enterprise offline deployment for Dograh. Read [ARCHITECTURE.md](./ARCHITECTURE.md) for the full design.

## Prerequisites

- Kubernetes 1.28+ (RKE2, OpenShift, vanilla kubeadm)
- NGINX Ingress Controller (internal LB)
- NVIDIA device plugin (for GPU inference)
- 500 Gi+ persistent storage (Postgres, MinIO, model weights)
- Private container registry

## 1. Load images (air-gap)

```bash
# On connected machine
./infra/on-prem/airgap/export-images.sh /tmp/dograh-images.tar

# On air-gapped cluster
./infra/on-prem/airgap/load-images.sh /tmp/dograh-images.tar registry.internal:5000
```

## 2. Secrets

```bash
kubectl create namespace dograh
kubectl create namespace dograh-inference
kubectl create namespace dograh-observability

# Option A: manual secret
kubectl -n dograh create secret generic dograh-onprem-secrets \
  --from-literal=OSS_JWT_SECRET="$(openssl rand -hex 32)" \
  --from-literal=POSTGRES_PASSWORD='...' \
  --from-literal=REDIS_PASSWORD='...' \
  --from-literal=DATABASE_URL='postgresql+asyncpg://...' \
  --from-literal=REDIS_URL='redis://:...@dograh-redis:6379'

# Option B: Vault via External Secrets (see secrets/)
kubectl apply -f infra/on-prem/secrets/
```

## 3. Deploy inference (GPU nodes)

```bash
kubectl apply -f infra/on-prem/inference/namespace.yaml
kubectl apply -f infra/on-prem/inference/vllm-deployment.yaml
kubectl apply -f infra/on-prem/inference/whisper-deployment.yaml
kubectl apply -f infra/on-prem/inference/tts-deployment.yaml
```

Edit `vllm-deployment.yaml` model name and PVC size before apply.

## 4. Deploy application

```bash
helm upgrade --install dograh ./infra/helm/dograh \
  --namespace dograh \
  -f infra/helm/dograh/values-on-prem.yaml \
  --set global.imageRegistry=registry.internal:5000 \
  --set secrets.existingSecret=dograh-onprem-secrets \
  --set secrets.create=false \
  --set ingress.hosts[0].host=voice.corp.internal
```

Or Kustomize:

```bash
cp infra/kubernetes/base/secret.example.yaml infra/kubernetes/base/secret.yaml
# edit secret.yaml
kubectl apply -k infra/kubernetes/overlays/on-prem/
```

## 5. Network isolation

```bash
kubectl apply -f infra/on-prem/tenant/network-policies.yaml
```

## 6. Observability

```bash
kubectl apply -f infra/on-prem/observability/namespace.yaml
kubectl apply -f infra/on-prem/observability/
```

Grafana: port-forward `svc/grafana` in `dograh-observability` (default admin password in `grafana-secret`).

## Verify

```bash
kubectl -n dograh get pods
curl -k https://voice.corp.internal/api/v1/health
curl -k https://voice.corp.internal/api/v1/realtime-observability/health/ready
```

Configure org AI settings to use in-cluster inference URLs from the `dograh-inference-routes` ConfigMap.

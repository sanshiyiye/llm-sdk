# Kubernetes Deployment

**Purpose:** Production deployment of LiteLLM Proxy  
**Tooling:** Kustomize + kubectl  
**Namespace:** `llm-system`

---

## STRUCTURE

```
k8s/
├── kustomization.yaml          # Kustomize entry point
└── litellm/
    ├── configmap.yaml          # Proxy config (config.yaml)
    ├── deployment.yaml         # 2 replicas, health checks, metrics port
    ├── service.yaml            # ClusterIP service (HTTP + metrics)
    ├── hpa.yaml                # Auto-scaling 2-6 replicas
    ├── secret.yaml.example     # Secret template (API keys)
    └── servicemonitor.yaml     # Prometheus ServiceMonitor
```

---

## DEPLOYMENT

```bash
# 1. Create namespace
kubectl create namespace llm-system

# 2. Create secrets (DO NOT commit to git)
kubectl create secret generic litellm-secrets \
  --namespace llm-system \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-... \
  --from-literal=OPENAI_API_KEY=sk-... \
  --from-literal=GEMINI_API_KEY=AI... \
  --from-literal=LITELLM_MASTER_KEY=sk-litellm-...

# 3. Deploy
kubectl apply -k k8s/

# 4. Verify
kubectl get pods -n llm-system
kubectl get svc -n llm-system
```

---

## CONFIGURATION

**ConfigMap** (`litellm/configmap.yaml`):
- Embeds `config/config.yaml` content
- Model definitions, fallback chains, routing rules

**Secrets** (`litellm/secret.yaml.example` → actual secret):
- Provider API keys (Anthropic, OpenAI, Gemini)
- LiteLLM master key for proxy authentication

**HPA** (`litellm/hpa.yaml`):
- Min: 2 replicas
- Max: 6 replicas
- Target CPU: 60%

---

## SERVICE ENDPOINT

```
# From within cluster (business services)
http://litellm-proxy.llm-system:4000

# External access (if LoadBalancer/NodePort configured)
http://<external-ip>:4000
```

---

## PROMETHEUS METRICS

**ServiceMonitor** (`litellm/servicemonitor.yaml`):
- Scrapes `/metrics` endpoint every 30s
- Requires Prometheus Operator in cluster
- Key metrics exposed:
  - `litellm_requests_total` — Total requests by model, status
  - `litellm_tokens_total` — Token usage by model, type (prompt/completion)
  - `litellm_request_duration_seconds` — Request latency histogram

**Metrics Port**: 9090 (exposed on deployment and service)

---

## NOTES

- Secrets are created via `kubectl create secret`, NOT in git
- `secret.yaml.example` is committed as a template only
- Config changes require `kubectl apply -k k8s/`
- HPA requires metrics-server in cluster
- Health checks on `/health/liveliness` and `/health/readiness`
- Prometheus metrics on `:9090/metrics` (if ServiceMonitor applied)

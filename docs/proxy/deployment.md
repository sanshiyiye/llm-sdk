# Proxy 部署手册

## 部署前置条件

- Kubernetes 1.28+
- 已安装 Kustomize
- 可访问外部模型提供商 HTTPS 出口
- 已准备 `litellm-secrets`
- 若启用审计日志，已准备 PostgreSQL 与 `DATABASE_URL`
- 若启用 Langfuse，已准备 `LANGFUSE_HOST`、`LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`

## Secret 准备

```bash
kubectl create secret generic litellm-secrets \
  --namespace llm-system \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-... \
  --from-literal=OPENAI_API_KEY=sk-openai-... \
  --from-literal=GEMINI_API_KEY=AIza... \
  --from-literal=SILICONFLOW_API_KEY=sk-siliconflow-... \
  --from-literal=LITELLM_MASTER_KEY=sk-litellm-... \
  --from-literal=DATABASE_URL=postgresql://postgres:postgres@postgres-rw.llm-system.svc.cluster.local:5432/litellm \
  --from-literal=LANGFUSE_HOST=https://cloud.langfuse.com \
  --from-literal=LANGFUSE_PUBLIC_KEY=pk-lf-... \
  --from-literal=LANGFUSE_SECRET_KEY=sk-lf-...
```

## 配置同步

```bash
python scripts/generate_k8s_configmap.py
```

## 部署

```bash
kubectl apply -k proxy/k8s/
kubectl rollout status deployment/litellm-proxy -n llm-system
```

## 部署后检查

```bash
kubectl get pods -n llm-system
kubectl get svc -n llm-system
kubectl logs deploy/litellm-proxy -n llm-system --tail=200
```

## 健康检查

```bash
kubectl port-forward -n llm-system svc/litellm-proxy 4000:4000
curl http://127.0.0.1:4000/health/liveliness
curl http://127.0.0.1:4000/health/readiness
```

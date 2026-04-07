# Proxy 回滚手册

## 回滚触发条件

- 发布后 10 分钟内错误率明显高于基线
- readiness 大面积失败
- 关键模型路由错误
- Langfuse 与 PostgreSQL 接入导致请求失败

## 回滚步骤

```bash
kubectl rollout undo deployment/litellm-proxy -n llm-system
kubectl rollout status deployment/litellm-proxy -n llm-system
```

## 指定版本回滚

```bash
kubectl rollout history deployment/litellm-proxy -n llm-system
kubectl rollout undo deployment/litellm-proxy --to-revision=<REVISION> -n llm-system
```

## 配置回滚

```bash
git checkout <stable-commit> -- proxy/config/config.yaml proxy/k8s/litellm/configmap.yaml
python scripts/generate_k8s_configmap.py
kubectl apply -k proxy/k8s/
```

## 回滚后确认

```bash
kubectl get pods -n llm-system
kubectl logs deploy/litellm-proxy -n llm-system --tail=200
kubectl port-forward -n llm-system svc/litellm-proxy 4000:4000
curl http://127.0.0.1:4000/health/readiness
```

## 记录要求

- 记录触发时间、触发原因、回滚 revision
- 记录回滚后 30 分钟错误率与延迟变化
- 若涉及 Secret 变更，补充审计说明

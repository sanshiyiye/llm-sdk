# Proxy 运维手册

本文档面向平台团队，介绍 LiteLLM Proxy 的日常运维操作。

---

## 目录

- [配置更新](#配置更新)
- [重启与滚动更新](#重启与滚动更新)
- [Secret 轮换](#secret-轮换)
- [健康检查](#健康检查)
- [日志与排障](#日志与排障)
- [扩缩容](#扩缩容)

---

## 配置更新

Proxy 配置文件位于 `proxy/config/config.yaml`，包含模型注册表、路由规则和 fallback 链。

### 添加新模型

在 `model_list` 下新增条目：

```yaml
model_list:
  - model_name: my-new-model          # SDK 使用的路由别名
    litellm_params:
      model: openai/gpt-4o            # provider/model 格式
      api_base: https://api.openai.com/v1
      api_key: os.environ/OPENAI_API_KEY
```

### 修改 capability 路由

Capability tag 到模型的映射通过 `model_name` 建立：

```yaml
# 将 auto-chat 改为指向新模型
- model_name: auto-chat
  litellm_params:
    model: openai/gpt-4o-mini
    api_key: os.environ/OPENAI_API_KEY
```

配置生效需要重启 Proxy（见下节）。

---

## 重启与滚动更新

### 本地开发环境

```bash
# 重启
docker compose -f proxy/docker-compose.dev.yaml restart

# 查看日志
docker compose -f proxy/docker-compose.dev.yaml logs -f

# 完全重建（配置大改时）
docker compose -f proxy/docker-compose.dev.yaml down && \
docker compose -f proxy/docker-compose.dev.yaml up -d
```

### Kubernetes 生产环境

```bash
# 滚动重启（不中断服务）
kubectl rollout restart deployment/litellm-proxy -n llm

# 查看滚动状态
kubectl rollout status deployment/litellm-proxy -n llm

# 验证 Pod 健康
kubectl get pods -n llm -l app=litellm-proxy
```

更新 `configmap/litellm-config` 后必须滚动重启才能生效：

```bash
kubectl create configmap litellm-config \
  --from-file=proxy/config/config.yaml \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl rollout restart deployment/litellm-proxy -n llm
```

---

## Secret 轮换

### 轮换 LITELLM_MASTER_KEY

1. 在 K8s Secret 中更新新 key：
   ```bash
   kubectl create secret generic litellm-secrets \
     --from-literal=LITELLM_MASTER_KEY=sk-new-master-key \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

2. 滚动重启 Proxy 使新 key 生效：
   ```bash
   kubectl rollout restart deployment/litellm-proxy -n llm
   ```

3. 通知各业务团队更新 `LLM_API_KEY`（如果 master key 也用作团队 key）。

### 轮换 Provider API Key（如 SiliconFlow）

```bash
kubectl create secret generic litellm-secrets \
  --from-literal=SILICONFLOW_API_KEY=sk-new-siliconflow-key \
  ... \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl rollout restart deployment/litellm-proxy -n llm
```

---

## 健康检查

Proxy 暴露两个健康检查端点：

| 端点 | 用途 | 说明 |
|------|------|------|
| `GET /health/readiness` | Kubernetes readiness probe | Proxy 进程存活且配置加载完成 |
| `GET /health/liveness` | Kubernetes liveness probe | Proxy 进程存活 |
| `GET /models` | 验证鉴权 | 返回已注册的模型列表，可用于验证 API key |

```bash
# 手动检查（生产环境替换 URL）
curl https://your-proxy.example.com/health/readiness
curl -H "Authorization: Bearer sk-your-key" https://your-proxy.example.com/models
```

使用 SDK 的 `doctor()` 方法可以一键检查完整链路：

```bash
python test_doctor.py
```

---

## 日志与排障

### 本地环境日志

```bash
docker compose -f proxy/docker-compose.dev.yaml logs -f litellm-proxy
```

### K8s 环境日志

```bash
kubectl logs -f deployment/litellm-proxy -n llm
kubectl logs -f deployment/litellm-proxy -n llm --previous  # 上一次 crash 的日志
```

### 常见问题

| 症状 | 可能原因 | 排查命令 |
|------|----------|---------|
| `HTTP 503` | Proxy 未启动或系统代理拦截 | `curl` 直接测试，排除客户端代理问题 |
| `HTTP 401` | API key 不匹配 | 检查 `LITELLM_MASTER_KEY` 与客户端 `LLM_API_KEY` |
| `HTTP 404 model not found` | 模型名未在 config.yaml 中注册 | 检查 `model_list` 中的 `model_name` |
| Proxy 启动后立即退出 | config.yaml 语法错误 | 查看 Proxy 启动日志 |
| Provider 返回 429 | 超出速率限制 | 检查 config.yaml 中的 `rpm_limit` 配置 |

---

## 扩缩容

K8s 部署使用 HPA，自动在 2-6 个副本之间伸缩（基于 CPU 负载）：

```bash
# 查看当前副本数
kubectl get hpa -n llm

# 手动调整副本（临时，HPA 会覆盖）
kubectl scale deployment/litellm-proxy --replicas=4 -n llm
```

如需调整 HPA 边界，修改 `proxy/k8s/hpa.yaml`。

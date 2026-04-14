# Proxy 运维手册

本文档面向平台团队，介绍 LiteLLM Proxy 的日常运维操作。

---

## 目录

- [配置更新](#配置更新)
- [重启与更新](#重启与更新)
- [更换 API Key](#更换-api-key)
- [健康检查](#健康检查)
- [日志与排障](#日志与排障)

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
      api_key: os.environ/OPENAI_API_KEY
```

### 修改 capability 路由

```yaml
# 将 auto-chat 改为指向新模型
- model_name: auto-chat
  litellm_params:
    model: openai/gpt-4o-mini
    api_key: os.environ/OPENAI_API_KEY
```

配置修改后需要重启 Proxy 才能生效（见下节）。

---

## 重启与更新

### 重启（配置变更后）

```bash
cd llm-sdk/proxy
git pull
docker compose --env-file .env.prod restart
```

### 升级 Proxy 版本

修改 `docker-compose.yaml` 中的镜像版本号，然后：

```bash
docker compose --env-file .env.prod pull
docker compose --env-file .env.prod up -d
```

---

## 更换 API Key

直接编辑 `.env.prod`，然后重启：

```bash
vim .env.prod
docker compose --env-file .env.prod up -d
```

---

## 健康检查

| 端点 | 用途 |
|------|------|
| `GET /health/readiness` | Proxy 就绪检查 |
| `GET /models` | 验证 API key 有效性 |

```bash
# Proxy 是否可达
curl http://localhost:4000/health/readiness

# API key 是否有效
curl -H "Authorization: Bearer <LITELLM_MASTER_KEY>" \
  http://localhost:4000/models
```

从业务侧一键诊断：

```bash
python test_doctor.py
```

---

## 日志与排障

```bash
# 实时日志
docker compose logs -f

# 最近 100 行
docker compose logs --tail=100
```

### 常见问题

| 症状 | 可能原因 | 排查方式 |
|------|----------|---------|
| `HTTP 503` | Proxy 未启动，或客户端系统代理拦截 | `curl` 直接测，排除代理问题 |
| `HTTP 401` | API key 不匹配 | 检查 `LITELLM_MASTER_KEY` 与客户端 `LLM_API_KEY` |
| `HTTP 404 model not found` | 模型名未在 config.yaml 注册 | 检查 `model_list` 中的 `model_name` |
| Proxy 启动后立即退出 | config.yaml 语法错误 | `docker compose logs` 查看启动日志 |
| Provider 返回 429 | 超出速率限制 | 检查 config.yaml 中的 `rpm_limit` 配置 |

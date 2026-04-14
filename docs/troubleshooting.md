# Troubleshooting

常见问题与解决方案。遇到问题时，**先运行 `client.doctor()`**，它会给出具体的修复建议。

---

## 快速诊断

```python
# Python
from llm_sdk import client
result = client.doctor()
result.print()
```

```typescript
// TypeScript
import { client } from '@goat/llm-sdk'
const result = await client.doctor()
result.print()
```

```go
// Go
result := c.Doctor(context.Background())
result.Print()
```

---

## 常见错误分类

### 配置缺失

**现象：** 请求报错 `LLM_BASE_URL not set` 或连接到 `http://localhost:4000` 但没有本地 Proxy

**修复：**
```bash
export LLM_BASE_URL=https://your-proxy.example.com
export LLM_API_KEY=sk-your-team-key
```

如果不知道 URL 和 Key，联系平台团队。

---

### Proxy 不可达

**现象：** `Connection refused` / `Network error` / `Doctor 检查: Proxy 不可达`

**可能原因 & 修复：**

| 原因 | 修复 |
|------|------|
| 使用了默认 `localhost:4000` 但没有本地 Proxy | 配置共享 Proxy URL，或启动本地 Proxy |
| 网络问题 / VPN 未连接 | 检查网络连接，确认能访问 Proxy 地址 |
| 本地 Proxy 未启动 | `docker compose -f proxy/docker-compose.dev.yaml up -d` |
| 本地 Proxy 未就绪 | `curl http://localhost:4000/health/readiness` 等待 healthy |
| Proxy 地址拼写错误 | 检查 `LLM_BASE_URL`，确认无多余空格或换行 |

---

### 鉴权失败（401 / 403）

**现象：** `AuthError: Authentication failed` / HTTP 401

**可能原因 & 修复：**

| 原因 | 修复 |
|------|------|
| `LLM_API_KEY` 未设置 | `export LLM_API_KEY=sk-your-key` |
| Key 与 Proxy 端 `LITELLM_MASTER_KEY` 不匹配 | 向平台团队确认正确的 Key |
| Key 已过期或被吊销 | 向平台团队申请新 Key |
| 本地 Proxy：Key 填写错误 | 检查 `proxy/.env` 中的 `LITELLM_MASTER_KEY` |

---

### 模型不存在（404 / ModelError）

**现象：** `Model not found` / `ProviderModelNotFoundError`

**可能原因 & 修复：**

| 原因 | 修复 |
|------|------|
| 用了 `local` capability 但没有本地 Ollama | 改用 `chat` 或 `fast` capability |
| `LLM_MODEL_CHAT` 设置了不存在的模型名 | 删除该环境变量，使用默认值 |
| 自建 Proxy 未配置该模型 | 在 `proxy/config/config.yaml` 中添加对应模型配置 |

---

### 限流（429）

**现象：** `RateLimitError: Rate limit exceeded`

SDK 会自动指数退避重试（默认 2 次）。如果持续出现：

- 检查请求频率是否过高
- 联系平台团队申请提高配额
- 考虑使用 `fast` capability（通常限流更宽松）

---

### 结构化输出解析失败

**现象：** `StructuredOutputError`

**修复：**
- 检查 Schema 定义是否简洁清晰
- 在 prompt 中明确要求输出 JSON 格式
- 尝试使用更强的模型（`capability="chat"` 而非 `capability="fast"`）

---

### 超时（TimeoutError）

**现象：** `TimeoutError: Request timed out`

**修复：**
```python
# 增大超时时间
from llm_sdk import LLMClient
client = LLMClient(timeout=120.0)
```

长文本生成、复杂推理任务建议使用流式接口：
```python
for chunk in client.chat_stream("写一篇长文章"):
    print(chunk, end="", flush=True)
```

---

## 仍未解决？

1. 确认 `client.doctor()` 输出的所有检查项
2. 查看 [共享 Proxy 接入](getting-started-shared.md) 或 [本地 Proxy 启动](getting-started-local.md)
3. 联系平台团队，提供 `doctor()` 的完整输出

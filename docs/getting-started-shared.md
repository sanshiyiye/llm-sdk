# 共享 Proxy 接入指南

> 适用场景：接入团队统一维护的 LiteLLM Proxy 实例（推荐默认路径）

---

## 前置条件

向平台团队申请以下两个配置项：

| 配置 | 说明 | 示例 |
|------|------|------|
| `LLM_BASE_URL` | 共享 Proxy 的 HTTP 地址 | `https://llm-proxy.internal.example.com` |
| `LLM_API_KEY` | 团队专属 API Key | `sk-team-abc123` |

---

## Python

### 安装

```bash
pip install llm-sdk
```

### 配置环境变量

```bash
# 方式 A：直接 export（本地开发）
export LLM_BASE_URL=https://llm-proxy.internal.example.com
export LLM_API_KEY=sk-team-abc123

# 方式 B：.env 文件（推荐本地开发）
cp sdk/python/.env.example .env
# 编辑 .env，填入 LLM_BASE_URL 和 LLM_API_KEY
```

### 首次调用

```python
from llm_sdk import client

reply = client.chat("你好")
print(reply["content"])
```

### 验证连接

```python
from llm_sdk import client

result = client.doctor()
result.print()
```

---

## TypeScript / Node.js

### 安装

```bash
npm install @goat/llm-sdk
```

### 配置环境变量

```bash
export LLM_BASE_URL=https://llm-proxy.internal.example.com
export LLM_API_KEY=sk-team-abc123
```

或在项目根目录创建 `.env`：

```env
LLM_BASE_URL=https://llm-proxy.internal.example.com
LLM_API_KEY=sk-team-abc123
```

### 首次调用

```typescript
import { client } from '@goat/llm-sdk'

const reply = await client.chat('你好')
console.log(reply.content)
```

### 验证连接

```typescript
import { client } from '@goat/llm-sdk'

const result = await client.doctor()
result.print()
```

---

## Go

### 安装

```bash
go get github.com/goat/llm-sdk/sdk/go
```

### 配置环境变量

```bash
export LLM_BASE_URL=https://llm-proxy.internal.example.com
export LLM_API_KEY=sk-team-abc123
```

### 首次调用

```go
package main

import (
    "context"
    "fmt"
    llmclient "github.com/goat/llm-sdk/sdk/go"
)

func main() {
    c := llmclient.New()
    reply, err := c.Chat(context.Background(), "你好", nil)
    if err != nil {
        panic(err)
    }
    fmt.Println(reply)
}
```

### 验证连接

```go
result := c.Doctor(context.Background())
result.Print()
```

---

## 常见问题

**Q: 拿到 URL 和 Key 后，还需要配置什么？**  
A: 不需要。SDK 默认使用 `chat` capability，直接调用即可。

**Q: 能指定用哪个模型吗？**  
A: 可以用 `capability` 参数选择场景（`fast`、`vision` 等），或通过环境变量 `LLM_MODEL_CHAT=gpt-4o` 覆盖具体模型。一般不需要。

**Q: 遇到鉴权错误怎么办？**  
A: 运行 `client.doctor()` 查看详细诊断，或参考 [Troubleshooting](troubleshooting.md)。

**Q: 我的请求走的是哪个模型？**  
A: 这由平台团队在 Proxy 侧配置。`chat` capability 默认走 `auto-chat`，支持多模型 fallback。业务层不需要关心。

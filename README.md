# LLM SDK

三分钟接入多语言 LLM，Python / TypeScript / Go 统一接口。

---

## 快速开始（3 分钟）

### 1. 获取连接信息

向平台团队申请：

```
LLM_BASE_URL=https://your-proxy.example.com
LLM_API_KEY=sk-your-team-key
```

### 2. 安装 SDK

```bash
# Python
pip install llm-sdk

# TypeScript / Node.js
npm install @goat/llm-sdk

# Go
go get github.com/goat/llm-sdk/sdk/go
```

### 3. 发起第一个请求

```python
# Python
import os
os.environ["LLM_BASE_URL"] = "https://your-proxy.example.com"
os.environ["LLM_API_KEY"] = "sk-your-team-key"

from llm_sdk import client
reply = client.chat("你好")
print(reply["content"])
```

```typescript
// TypeScript
import { client } from '@goat/llm-sdk'

const reply = await client.chat('你好')
console.log(reply.content)
```

```go
// Go
c := llmclient.New() // 读取 LLM_BASE_URL / LLM_API_KEY 环境变量
reply, _ := c.Chat(ctx, "你好", nil)
fmt.Println(reply)
```

**就这些。** 不需要了解 LiteLLM、不需要配置模型名、不需要管理 API Key。

---

## 诊断问题

遇到连接问题时运行：

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
result := c.Doctor(ctx)
result.Print()
```

输出示例：

```
LLM SDK Doctor
==============
✓  LLM_BASE_URL       已配置 (https://your-proxy.example.com)
✓  LLM_API_KEY        已配置
✓  Proxy 可达          HTTP 200 /health/readiness
✓  鉴权有效            chat 请求成功
✓  Capability 配置     7 个 tag 均有效

全部通过，SDK 可正常使用。
```

---

## 常用 API

```python
# Python 示例（TypeScript / Go 接口相同）

# 基础对话
reply = client.chat("你好")["content"]

# 快速模型（延迟敏感）
reply = client.chat("快速回答", capability="fast")["content"]

# 视觉理解
reply = client.chat("描述这张图", image_url="https://example.com/img.png")["content"]

# 流式输出
for chunk in client.chat_stream("写一篇文章"):
    print(chunk, end="", flush=True)

# 结构化输出（Pydantic）
from pydantic import BaseModel
class Product(BaseModel):
    name: str
    price: float

result = client.chat_structured("提取：iPhone 16 Pro 售价 7999", schema=Product)
print(result.name, result.price)

# 多轮会话
session = client.session(system="你是代码审查助手")
r1 = session.chat("审查这段代码：...")
r2 = session.chat("给出修复方案")

# 文本向量化
vec = client.embed("some text")

# 图像生成
url = client.image_gen("a cat on the moon")
```

---

## Capability Tag 体系

业务代码用 tag，不写死模型名：

| tag | 默认模型 | 适用场景 | 生产可用 |
|-----|---------|---------|---------|
| `chat` | auto-chat | 普通对话，含 fallback | ✓ |
| `vision` | auto-vision | 图片理解（有图片时自动推断） | ✓ |
| `video-input` | gemini-vision | 视频帧分析 | ✓ |
| `embedding` | text-embedding | 文本向量化 | ✓ |
| `image-gen` | gpt-image-gen | 图像生成 | ✓ |
| `fast` | gemini-chat | 延迟敏感场景 | ✓ |
| `local` | local-chat | 本地 / 内网模型 | **仅开发** |

**需要换模型？** 用环境变量覆盖，不改代码：

```bash
LLM_MODEL_CHAT=gpt-4o        # 覆盖 chat tag 对应的模型
LLM_MODEL_FAST=gemini-flash  # 覆盖 fast tag
```

---

## 本地开发

需要在本地跑完整的 Proxy？一条命令：

```bash
cp proxy/.env.example proxy/.env   # 填入 provider API key
docker compose -f proxy/docker-compose.dev.yaml up -d
```

等 readiness 就绪后正常使用 SDK（`LLM_BASE_URL=http://localhost:4000`）。

详见 [本地开发指南](docs/getting-started-local.md)。

---

## 接入路径选择

| 情况 | 推荐路径 |
|------|---------|
| 接入团队共享平台 | [共享 Proxy 接入](docs/getting-started-shared.md)（推荐） |
| 本地开发 / 自建 Proxy | [本地 Proxy 启动](docs/getting-started-local.md) |
| 遇到连接 / 鉴权问题 | 运行 `client.doctor()` |
| 更多常见问题 | [Troubleshooting](docs/troubleshooting.md) |

---

## 运行测试

```bash
# Python
cd sdk/python && pytest tests/ -v

# TypeScript
cd sdk/typescript && npm test

# Go
cd sdk/go && go test ./... -v
```

---

## 生产部署（Kubernetes）

```bash
# 创建 secret（不进 git）
kubectl create secret generic litellm-secrets \
  --namespace llm-system \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-... \
  --from-literal=OPENAI_API_KEY=sk-... \
  --from-literal=GEMINI_API_KEY=AI... \
  --from-literal=LITELLM_MASTER_KEY=sk-litellm-...

# 一键部署
kubectl apply -k proxy/k8s/

# 业务服务通过集群 DNS 访问
# LLM_BASE_URL=http://litellm-proxy.llm-system:4000
```

详见 [架构设计](docs/llm-sdk-design.md) | [Proxy 运维手册](docs/proxy-ops.md) | [发布检查清单](docs/release-checklist.md)

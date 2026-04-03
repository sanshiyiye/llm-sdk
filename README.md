# LLM SDK

多语言 LLM 内部 SDK，Python / TypeScript / Go 三端统一接口，通过 LiteLLM Proxy 路由到 Anthropic、OpenAI、Gemini、Ollama 等模型。

---

## 架构总览

```
业务代码 (L1)
  ↓  chat() / embed() / image_gen()
SDK 层 (L2)  llm_client.py · llm_client.ts · llm_client.go
  ↓  capability tag → model_name
LiteLLM Proxy (L3)  localhost:4000 | litellm-proxy.llm-system:4000
  ↓  模型路由 · fallback · Key 管理
模型 API (L4)  Anthropic · OpenAI · Gemini · Ollama
```

---

## 快速开始

### 1. 启动 Proxy（开发环境）

```bash
pip install "litellm[proxy]"
cp .env.example .env          # 填入 API Keys
litellm --config config/config.yaml --port 4000
```

### 2. Python

```bash
cd python
pip install -e ".[dev]"
```

```python
from llm_sdk import client, templates
from pydantic import BaseModel

# 基础对话
reply = client.chat("你好")

# 指定能力
reply = client.chat("快速回答", capability="fast")

# 视觉（自动推断）
reply = client.chat("描述图片", image_url="https://example.com/img.png")

# 流式输出
for chunk in client.chat_stream("写一篇文章"):
    print(chunk, end="", flush=True)

# 结构化输出
class Product(BaseModel):
    name: str
    price: float

result = client.chat_structured("提取：iPhone 16 Pro 售价 7999", schema=Product)
print(result.name, result.price)

# 多轮会话
session = client.session(system="你是代码审查助手")
r1 = session.chat("审查这段代码：...")
r2 = session.chat("给出修复方案")

# Prompt 模板
templates.load_dir("prompts/")
reply = templates.chat_with_template(client, "code_review",
    language="Python", focus="内存泄漏", code="x = []")
```

### 3. TypeScript / Node.js

```bash
cd typescript
npm install
```

```typescript
import { client, templates } from './index'
import { z } from 'zod'

// 基础对话
const reply = await client.chat('你好')

// 流式输出
for await (const chunk of client.chatStream('写一篇文章')) {
  process.stdout.write(chunk)
}

// 结构化输出
const schema = z.object({ name: z.string(), price: z.number() })
const result = await client.chatStructured('提取商品信息', schema)

// 多轮会话
const sess = client.session('你是代码审查助手')
const r1 = await sess.chat('审查这段代码：...')
const r2 = await sess.chat('给出修复方案')

// Prompt 模板
templates.loadDir('prompts/')
const reply2 = await templates.chatWithTemplate(client, 'code_review',
  { language: 'TypeScript', focus: '类型安全', code: 'const x = 1' })
```

### 4. Go

```bash
cd go
go test ./...
```

```go
package main

import (
    "context"
    "fmt"
    "github.com/yourorg/llm-sdk/go"
)

func main() {
    ctx := context.Background()
    c := llmclient.New()

    // 基础对话
    reply, _ := c.Chat(ctx, "你好", nil)
    fmt.Println(reply)

    // 流式输出
    chunks, errc := c.ChatStream(ctx, "写一篇文章", nil)
    for chunk := range chunks { fmt.Print(chunk) }
    if err := <-errc; err != nil { panic(err) }

    // 结构化输出
    type Product struct {
        Name  string  `json:"name"`
        Price float64 `json:"price"`
    }
    var p Product
    _ = c.ChatStructured(ctx, "提取：iPhone 售价 7999", &p, nil)
    fmt.Println(p.Name, p.Price)

    // 多轮会话
    sess := c.NewSession("你是代码审查助手")
    r1, _ := sess.Chat(ctx, "审查这段代码：...", nil)
    r2, _ := sess.Chat(ctx, "给出修复方案", nil)
    fmt.Println(r1, r2)

    // Prompt 模板
    reg := llmclient.NewTemplateRegistry()
    reg.LoadDir("../prompts")
    result, _ := reg.ChatWithTemplate(ctx, c, "code_review",
        map[string]string{"language": "Go", "focus": "并发安全", "code": "var x int"},
        nil)
    fmt.Println(result)
}
```

---

## Capability Tag 体系

| tag | 默认 model | 说明 | 生产可用 |
|-----|-----------|------|---------|
| `chat` | `auto-chat` | 普通对话，含 fallback | ✓ |
| `vision` | `auto-vision` | 图片理解（自动推断） | ✓ |
| `video-input` | `gemini-vision` | 视频帧分析 | ✓ |
| `embedding` | `text-embedding` | 文本向量化 | ✓ |
| `image-gen` | `gpt-image-gen` | 图像生成 | ✓ |
| `fast` | `gemini-chat` | 延迟敏感场景 | ✓ |
| `local` | `local-chat` | 本地/内网模型 | 仅开发 |

所有 tag 可通过环境变量覆盖：`LLM_MODEL_CHAT`, `LLM_MODEL_VISION`, ...

---

## 运行测试

```bash
# Python
cd python && pytest tests/ -v

# TypeScript
cd typescript && npm test

# Go
cd go && go test ./... -v
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
kubectl apply -k k8s/

# 业务服务通过集群 DNS 访问
# http://litellm-proxy.llm-system:4000
```

详细部署说明见 `docs/llm-sdk-design.md`。

---

## v0.3.0 新特性

### 请求级缓存（Request-level Caching）

相同 prompt + model 自动命中缓存，节省 Token 费用：

```python
# Python
from llm_sdk import LLMClient
c = LLMClient()

# 首次调用 → 访问 API
r1 = c.chat("解释量子计算")

# 相同调用 → 命中缓存，零 Token 消耗
r2 = c.chat("解释量子计算")  # 瞬间返回，带 _cached: true 标记
```

```typescript
// TypeScript
const reply = await client.chat('解释量子计算', { cache: true })
```

### Tool Use / Function Calling

让 LLM 调用你的业务函数：

```python
# Python
from llm_sdk import client
from llm_sdk.tools import llm_tool

@llm_tool
def get_weather(city: str) -> str:
    """获取城市天气"""
    return weather_api.fetch(city)

# SDK 自动处理：LLM 请求工具 → 执行函数 → 返回结果
reply = client.chat_with_tools("北京今天天气如何？", tools=[get_weather])
```

```go
// Go
type WeatherTool struct{}
func (w WeatherTool) Execute(ctx context.Context, params interface{}) (string, error) {
    return "Sunny", nil
}
c.ChatWithTools(ctx, "北京天气如何？", tool, nil)
```

### Prometheus 指标监控

K8s 部署已内置 Prometheus ServiceMonitor：

```bash
# 部署后自动暴露指标
kubectl port-forward -n llm-system svc/litellm-proxy 9090:9090
curl localhost:9090/metrics
```

关键指标：
- `litellm_requests_total` — 按模型、状态统计请求数
- `litellm_tokens_total` — Token 消耗统计
- `litellm_request_duration_seconds` — 请求延迟分布

---

## 目录结构

```
llm-sdk/
├── config/
│   └── config.yaml          # 模型配置（提交 git）
├── python/                  # Python SDK (v0.3.0)
│   ├── __init__.py
│   ├── client.py            # 核心 client + 缓存
│   ├── cache.py             # 请求级缓存
│   ├── tools.py             # Tool Use / Function Calling
│   ├── errors.py            # 错误体系
│   ├── session.py           # 多轮会话
│   ├── structured.py        # 结构化输出
│   ├── templates.py         # Prompt 模板
│   └── tests/
├── typescript/              # TypeScript SDK (v0.3.0)
│   ├── index.ts
│   ├── client.ts            # 核心 client + 缓存
│   ├── cache.ts             # 请求级缓存
│   ├── tools.ts             # Tool Use / Function Calling
│   ├── errors.ts
│   ├── session.ts
│   ├── structured.ts
│   ├── templates.ts
│   └── tests/
├── go/                      # Go SDK (v0.3.0)
│   ├── client.go
│   ├── cache.go             # 请求级缓存
│   ├── tools.go             # Tool Use / Function Calling
│   ├── errors.go
│   ├── session.go
│   ├── structured.go
│   ├── templates.go
│   └── client_test.go
├── k8s/                     # Kubernetes Manifests (v0.3.0)
│   ├── kustomization.yaml
│   └── litellm/
│       ├── servicemonitor.yaml  # Prometheus 监控
│       └── ...
├── prompts/                 # Prompt 模板文件
├── tests/
│   └── integration/         # 三语言统一集成测试 (v0.3.0)
├── docs/
│   ├── llm-sdk-design.md
│   └── llm-sdk-devplan.md
├── CHANGELOG.md             # 版本变更记录 (v0.3.0)
├── .env.example
└── .gitignore
```

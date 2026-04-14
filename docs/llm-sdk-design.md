# LLM 内部 SDK 系统设计规划

> 目标：一次设计，Python / Node.js / Go 三语言复用，彻底消除每个项目重复编写大模型调用代码的问题。
>
> 部署选型：LiteLLM Proxy 以独立容器运行在 Kubernetes，业务服务通过集群内 DNS 访问。

---

## 一、系统全局架构

```
┌──────────────────────────────────────────────────────────────────┐
│  L1  业务层    Python Agent · Node.js Tool · Go Service          │
│               只知道 chat() / embed() / image_gen()              │
├──────────────────────────────────────────────────────────────────┤
│  L2  SDK 层   llm_client.py · llm_client.ts · llm_client.go     │
│               capability tag 路由 · 结构化输出 · 会话管理        │
├──────────────────────────────────────────────────────────────────┤
│  L3  路由层   LiteLLM Proxy                                      │
│               开发：localhost:4000                               │
│               生产：http://<服务器IP>:4000                      │
│               模型路由 · fallback · Key 集中管理 · 限流          │
├──────────────────────────────────────────────────────────────────┤
│  L4  模型层   Anthropic · OpenAI · Gemini · Ollama(仅开发)      │
└──────────────────────────────────────────────────────────────────┘
```

**核心原则：每层只负责一件事，变化只在本层内消化。**

| 变化类型 | 修改位置 | 其他层是否感知 |
|---------|---------|-------------|
| 换模型供应商 | `config.yaml` | 否 |
| 切换具体模型别名 | 环境变量 `LLM_MODEL_*` | 否 |
| 新增业务语义/能力 | SDK 层 | 否 |
| 业务逻辑变更 | L1 业务层 | 否 |

---

## 二、capability tag 体系（贯穿全系统的核心约定）

tag 是业务层表达「需要什么能力」的唯一词汇，在 SDK 层转换为 model_name，再由 Proxy 路由到实际模型。**此表是整个系统的唯一约定来源，config.yaml 和 SDK TAG_MODEL_MAP 两处必须与此表保持一致。**

```
capability tag  SDK 默认 model_name    config.yaml 实际模型               生产可用
────────────────────────────────────────────────────────────────────────────────────
chat            auto-chat             anthropic/claude-sonnet-4-5         ✓
                                      fallback → gpt-chat
vision          auto-vision           anthropic/claude-opus-4-5           ✓
                                      fallback → gpt-vision
video-input     gemini-vision         gemini/gemini-2.0-flash             ✓
                                      (无 fallback)
embedding       text-embedding        openai/text-embedding-3-small       ✓
                                      (无 fallback)
image-gen       gpt-image-gen         openai/dall-e-3                     ✓
                                      (无 fallback)
fast            gemini-chat           gemini/gemini-2.0-flash             ✓
                                      fallback → gpt-chat
local           local-chat            ollama/llama3.2                   仅开发
                                      (无 fallback)
```

---

## 三、各层详细设计

### L4 模型层（providers）

持有真实 API 凭证，不做任何额外处理。

| 提供商 | 连接方式 | 必需配置 | 环境 |
|--------|---------|---------|------|
| Anthropic | 官方 API / 中转 base_url | `ANTHROPIC_API_KEY` | 开发 + 生产 |
| OpenAI | 官方 / Azure / 兼容接口 | `OPENAI_API_KEY` | 开发 + 生产 |
| Gemini | Google AI API | `GEMINI_API_KEY` | 开发 + 生产 |
| Ollama | 本地 HTTP，无需 key | `base_url: http://localhost:11434` | **仅开发** |

---

### L3 路由层（LiteLLM Proxy）

负责：模型路由、fallback、限流、API Key 集中管理。业务服务只向 Proxy 发请求，**不直接持有任何厂商 API Key**。

#### config.yaml（开发/生产共用，提交 git）

```yaml
# =============================================================
# LiteLLM Proxy 模型配置
# 不含 secrets，可提交 git
# API Key 全部通过环境变量注入（os.environ/VAR_NAME）
# =============================================================

model_list:

  # ── 智能路由组（业务层首选，内置 fallback）─────────────────

  - model_name: auto-chat
    litellm_params:
      model: anthropic/claude-sonnet-4-5
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      mode: chat
      tags: [chat, auto]

  - model_name: auto-vision
    litellm_params:
      model: anthropic/claude-opus-4-5
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      mode: chat
      supports_vision: true
      tags: [vision, auto]

  # ── 各厂商具体模型（fallback 备选 / 直接调用）───────────────

  - model_name: gpt-chat
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
    model_info:
      mode: chat
      tags: [chat, openai]

  - model_name: gpt-vision
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
    model_info:
      mode: chat
      supports_vision: true
      tags: [vision, openai]

  - model_name: gemini-chat
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY
    model_info:
      mode: chat
      tags: [chat, fast, gemini]

  - model_name: gemini-vision
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY
    model_info:
      mode: chat
      supports_vision: true
      supports_video: true
      tags: [vision, video-input, gemini]

  - model_name: text-embedding
    litellm_params:
      model: openai/text-embedding-3-small
      api_key: os.environ/OPENAI_API_KEY
    model_info:
      mode: embedding
      tags: [embedding]

  - model_name: gpt-image-gen
    litellm_params:
      model: openai/dall-e-3
      api_key: os.environ/OPENAI_API_KEY
    model_info:
      mode: image_generation
      tags: [image-gen]

  # ── 本地模型（仅开发，生产中定义保留但 fallback 链不引用）──

  - model_name: local-chat
    litellm_params:
      model: ollama/llama3.2
      base_url: http://localhost:11434
    model_info:
      mode: chat
      tags: [chat, local]

# ── 路由策略 ──────────────────────────────────────────────────

router_settings:
  routing_strategy: simple-shuffle
  num_retries: 2
  timeout: 30
  retry_after: 3
  fallbacks:
    # 开发环境 local-chat 可生效；生产中 Ollama 不可达会跳过
    - auto-chat:   [gpt-chat, local-chat]
    - auto-vision: [gpt-vision]
    - gemini-chat: [gpt-chat]

# ── 全局设置 ──────────────────────────────────────────────────

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  rpm_limit: 500
  tpm_limit: 1000000
  request_timeout: 60
  default_fallbacks: [gpt-chat]
```

#### 启动方式

```bash
# 开发环境（本地进程，读取 proxy/.env 中的 API Keys）
pip install "litellm[proxy]"
python proxy/start_proxy.py

# 生产环境：Kubernetes，见第六章
```

---

### L2 SDK 层（内部 SDK）

负责：capability tag → model_name 映射、统一接口封装、错误处理。  
**不持有任何厂商 API Key，只持有访问 Proxy 的 `LLM_API_KEY`（即 LITELLM_MASTER_KEY 的值）。**

#### 核心接口契约（三语言语义一致）

```
# 基础能力（阶段一）
chat(prompt, options?)               → string
embed(text | text[])                 → float[] | float[][]
image_gen(prompt, options?)          → string (url)

# 增强能力（阶段二）
chat_structured(prompt, schema)      → T（强类型对象）
chat_stream(prompt, options?)        → AsyncIterator<string>
session(system?)                     → Session

# Session 对象（阶段二）
session.chat(prompt, options?)       → string
session.chat_structured(prompt, schema) → T
session.chat_stream(prompt)          → AsyncIterator<string>
session.clear()                      → void
```

#### TAG_MODEL_MAP（与第二章 tag 体系严格对应）

```
SDK 内部维护，读环境变量，有默认值：

  "chat"        → LLM_MODEL_CHAT        ?? "auto-chat"
  "vision"      → LLM_MODEL_VISION      ?? "auto-vision"
  "video-input" → LLM_MODEL_VIDEO       ?? "gemini-vision"
  "embedding"   → LLM_MODEL_EMBEDDING   ?? "text-embedding"
  "image-gen"   → LLM_MODEL_IMAGE_GEN   ?? "gpt-image-gen"
  "fast"        → LLM_MODEL_FAST        ?? "gemini-chat"
  "local"       → LLM_MODEL_LOCAL       ?? "local-chat"

model_name 解析优先级（从高到低）：
  1. model 参数直接指定（绕过 tag 路由）
  2. capability 参数手动指定
  3. 自动推断：有图像/视频输入 → "vision"，否则 → "chat"
```

#### 调用示例（三语言对照）

```python
# Python
from llm_sdk import client

reply = client.chat("总结这篇文章")                        # 自动推断 chat
reply = client.chat("快速回答", capability="fast")         # 手动指定
reply = client.chat("图里有什么", image_url="https://...") # 自动推断 vision
reply = client.chat("分析视频", image_url="...", capability="video-input")
vec   = client.embed("some text")
url   = client.image_gen("未来城市，赛博朋克风格")
reply = client.chat("你好", model="gpt-chat")              # 直接指定 model_name

# 多轮会话（阶段二）
session = client.session(system="你是一个代码审查助手")
r1 = session.chat("审查这段代码：...")
r2 = session.chat("针对第一个问题给出修复方案")

# 结构化输出（阶段二）
from pydantic import BaseModel
class Product(BaseModel):
    name: str
    price: float
result = client.chat_structured("提取：iPhone 16 Pro 售价 7999", schema=Product)
```

```typescript
// Node.js / TypeScript
import { client } from '@goat/llm-sdk'
const reply  = await client.chat('总结这篇文章')
const reply2 = await client.chat('快速回答', { capability: 'fast' })
const reply3 = await client.chat('图里有什么', { imageUrl: 'https://...' })
const vec    = await client.embed('some text')
const url    = await client.imageGen('未来城市')
```

```go
// Go
c := llmclient.New()
reply,  _ := c.Chat(ctx, "总结这篇文章", nil)
reply2, _ := c.Chat(ctx, "快速回答", &llmclient.ChatOpts{Capability: "fast"})
reply3, _ := c.Chat(ctx, "图里有什么", &llmclient.ChatOpts{ImageURL: "https://..."})
vec,    _ := c.Embed(ctx, "some text", nil)
```

---

### L1 业务层

只表达业务意图，不出现任何模型名、API Key、厂商字样。

```python
# 正确：只说"我要什么"
reply = client.chat("帮我总结会议记录", capability="fast")
vec   = client.embed(article_text)
img   = client.image_gen("产品主图，简约白底")

# 错误：硬编码模型细节
import anthropic
c = anthropic.Anthropic(api_key="sk-ant-...")  # ← 不应出现在业务层
```

---

## 四、配置与环境体系

### 4.1 两套环境配置对比

| 配置项 | 开发环境 | 生产（Linux 服务器） |
|-------|---------|--------------------|
| config.yaml 加载方式 | 本地文件，`litellm --config` | Docker volume 挂载 |
| 厂商 API Keys | 本地 `.env` | 服务器 `.env.prod` |
| `LITELLM_MASTER_KEY` | 本地 `.env` | 服务器 `.env.prod` |
| Proxy 地址（业务侧） | `http://localhost:4000` | `http://<服务器IP>:4000` |
| `LLM_API_KEY`（业务侧） | 本地 `.env` | 各服务自己的 `.env` |
| `LLM_MODEL_*` tag 覆盖 | 本地 `.env` | 各服务自己的 `.env` |
| `local` tag 可用性 | **可用**（本地跑 Ollama） | **不可用**（服务器无 Ollama） |

### 4.2 本地 .env（仅开发，加入 .gitignore）

```bash
# ── Proxy 进程读取（厂商 API Keys）───────────────────────────
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AI...
LITELLM_MASTER_KEY=sk-litellm-master-dev

# ── 业务代码 / SDK 层读取 ─────────────────────────────────────
LLM_BASE_URL=http://localhost:4000
LLM_API_KEY=sk-litellm-master-dev    # 与 LITELLM_MASTER_KEY 相同

# capability tag 覆盖（不填则使用 SDK 默认值）
LLM_MODEL_CHAT=auto-chat
LLM_MODEL_VISION=auto-vision
LLM_MODEL_VIDEO=gemini-vision
LLM_MODEL_EMBEDDING=text-embedding
LLM_MODEL_IMAGE_GEN=gpt-image-gen
LLM_MODEL_FAST=gemini-chat
LLM_MODEL_LOCAL=local-chat
```

### 4.3 .env.example（提交 git）

```bash
# 复制为 proxy/.env 后填入真实值
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=
LITELLM_MASTER_KEY=

LLM_BASE_URL=http://localhost:4000
LLM_API_KEY=                         # 填入与 LITELLM_MASTER_KEY 相同的值

LLM_MODEL_CHAT=
LLM_MODEL_VISION=
LLM_MODEL_VIDEO=
LLM_MODEL_EMBEDDING=
LLM_MODEL_IMAGE_GEN=
LLM_MODEL_FAST=
LLM_MODEL_LOCAL=
```

---

## 五、项目目录结构

```
my-llm-sdk/
│
├── sdk/
│   ├── python/
│   │   ├── llm_sdk/
│   │   ├── tests/
│   │   └── pyproject.toml
│   ├── typescript/
│   │   ├── index.ts
│   │   ├── session.ts
│   │   ├── structured.ts
│   │   └── tests/
│   ├── go/
│   │   ├── client.go
│   │   ├── session.go
│   │   ├── structured.go
│   │   └── client_test.go
│   ├── prompts/
│   ├── examples/
│   └── compat-tests/
│
├── proxy/
│   ├── config/
│   │   └── config.yaml          # Proxy 模型定义（提交 git）
│   ├── docker-compose.yaml      # 生产部署（Linux 服务器）
│   ├── docker-compose.dev.yaml  # 本地开发
│   ├── .env.prod.example        # 生产环境模板（提交 git）
│   ├── .env.example             # 本地开发环境模板（提交 git）
│   └── start_proxy.py
│
├── proxy/.env.prod              # 生产真实密钥（.gitignore）
├── proxy/.env                   # 本地真实密钥（.gitignore）
├── .gitignore
└── README.md
```

`.gitignore` 必须包含：

```
proxy/.env
proxy/.env.prod
```

---

## 六、生产部署（Linux 服务器）

### 6.1 部署方式

LiteLLM Proxy 以 Docker 容器运行在 Linux 服务器上，业务服务通过 IP + 端口直接访问：

```
Linux Server
│
└── Docker: litellm-proxy (port 4000)
    └── config: proxy/config/config.yaml（挂载只读）
    └── secrets: proxy/.env.prod（环境变量注入，不进 git）

业务服务 → http://<服务器IP>:4000
```

### 6.2 文件说明

| 文件 | 用途 | 是否进 git |
|------|------|-----------|
| `proxy/config/config.yaml` | 模型注册表、路由规则 | ✓ |
| `proxy/docker-compose.yaml` | 生产容器定义 | ✓ |
| `proxy/.env.prod.example` | 环境变量模板 | ✓ |
| `proxy/.env.prod` | 真实 API key | **✗ 不进 git** |

### 6.3 首次部署

```bash
git clone <repo> llm-sdk && cd llm-sdk/proxy
cp .env.prod.example .env.prod   # 填写真实 API key
docker compose --env-file .env.prod up -d
curl http://localhost:4000/health/readiness
```

### 6.4 运维操作速查

```bash
# 更新模型配置（改 config.yaml 后）
git pull
docker compose --env-file .env.prod restart

# 升级 LiteLLM 版本（改 docker-compose.yaml image tag 后）
docker compose --env-file .env.prod pull
docker compose --env-file .env.prod up -d

# 查看日志
docker compose logs -f

# 更换 API key
vim .env.prod
docker compose --env-file .env.prod restart
```

详见 [Linux 部署指南](deploy-linux.md)。

---

## 七、capability 使用决策表

| 使用场景 | capability | 对应 model_name | 生产可用 |
|---------|-----------|----------------|---------|
| 普通问答、摘要、翻译、代码 | `chat` | `auto-chat` | ✓ |
| 图片理解、OCR、截图分析 | `vision`（或自动推断） | `auto-vision` | ✓ |
| 视频帧分析 | `video-input` | `gemini-vision` | ✓ |
| 批量文本向量化 | `embedding` | `text-embedding` | ✓ |
| 生成配图 | `image-gen` | `gpt-image-gen` | ✓ |
| 延迟敏感、快速响应 | `fast` | `gemini-chat` | ✓ |
| 离线调试、隐私数据 | `local` | `local-chat` | **仅开发** |
| 绕过 tag 路由 | `model="gpt-chat"` | — | ✓ |

---

## 八、能力演进路线

### 阶段一（已完成）
- [x] 三语言基础 `chat` / `embed` / `image_gen`
- [x] 7 个 capability tag + 自动 capability 推断
- [x] 多模态图片输入（vision）、视频输入（video-input）
- [x] `config.yaml` 完整模型配置（含 fallback 链）
- [x] 开发 `.env` + 生产 `.env.prod` 双环境配置体系
- [x] Docker Compose 生产部署 + 本地开发一键启动

### 阶段二（近期）
- [ ] 结构化输出（Python Pydantic / TS Zod / Go struct tag）
- [ ] 多轮会话 `Session` 对象
- [ ] Prompt 模板管理器（文件加载 + 变量替换）
- [ ] 流式输出 `chat_stream`（async generator，三语言一致）
- [ ] 错误分类与重试（限流 429 / 网络超时 / 模型错误 → 差异化处理）

### 阶段三（中期）
- [ ] 请求级缓存（相同 prompt + model → 命中缓存，省 token）
- [ ] Token 用量统计（按服务 / 按模型计数，写入 Prometheus）
- [ ] 三语言统一集成测试套件（验证接口语义一致性）
- [ ] Tool use / Function calling 封装

### 阶段四（成熟期）
- [ ] 可观测性接入（Langfuse 或 Helicone）
- [ ] 自动评估（A/B 测试不同模型在同一任务上的输出质量）
- [ ] 请求审计日志（持久化到 PostgreSQL）
- [ ] 多集群 / 跨地域 Proxy 高可用

---

## 九、关键设计决策记录

**tag 路由为什么在 SDK 层而不在 Proxy 层？**
LiteLLM Proxy 按 `model_name` 路由，不接受 tag 作为路由键。`capability → model_name` 的映射属于业务语义，放在 SDK 内并由环境变量覆盖。Proxy 只负责「已知 model_name 时如何找到真实模型并做 fallback」。

**为什么加 SDK 层而不直接用 LiteLLM Python 库？**
LiteLLM 库解决「多厂商格式统一」，SDK 层解决「业务语义抽象 + 跨语言复用 + 统一接口契约」。两个问题层次不同。用 Proxy 模式后 SDK 层极薄，三语言都只做 HTTP 调用，不依赖 LiteLLM Python 包，Go 和 Node.js 服务也能复用同一套能力抽象。

**config.yaml 开发/生产为什么共用一份？**
模型定义本身与环境无关，API Keys 通过各自的环境变量文件（`.env` / `.env.prod`）注入。共用一份 config.yaml 消除维护分叉风险。

**`local` tag 为什么在生产中不可用？**
Ollama 运行在开发者本机，生产服务器上没有 Ollama。业务服务若在生产调用 `local` capability，Proxy 会因为 `local-chat` 的 `base_url`（localhost:11434）不可达而报错——这是有意为之的硬约束，防止隐私数据意外路由到公网模型。

**业务服务的 `LLM_API_KEY` 如何管理？**
各业务服务在自己的 `.env` 文件中配置 `LLM_API_KEY`，值与 Proxy 端的 `LITELLM_MASTER_KEY` 一致。`.env` 文件不进 git，通过人工或部署脚本分发。

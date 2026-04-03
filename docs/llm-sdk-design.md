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
│               生产：litellm-proxy.llm-system:4000 (K8s)         │
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

tag 是业务层表达「需要什么能力」的唯一词汇，在 SDK 层转换为 model_name，再由 Proxy 路由到实际模型。**此表是整个系统的唯一约定来源，config.yaml、SDK TAG_MODEL_MAP、K8s ConfigMap 三处必须与此表保持一致。**

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
# 开发环境（本地进程，读取 .env 中的 API Keys）
pip install "litellm[proxy]"
litellm --config config/config.yaml --port 4000

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
from llm_client import client

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
import { client } from './llm_client'
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

| 配置项 | 开发环境 | 生产（K8s） |
|-------|---------|------------|
| config.yaml 加载方式 | 本地文件，`litellm --config` | K8s ConfigMap，挂载到 Pod |
| 厂商 API Keys | 本地 `.env` | K8s Secret `litellm-secrets` |
| `LITELLM_MASTER_KEY` | 本地 `.env` | K8s Secret `litellm-secrets` |
| Proxy 地址（业务侧） | `http://localhost:4000` | `http://litellm-proxy.llm-system:4000` |
| `LLM_API_KEY`（业务侧） | 本地 `.env` | K8s Secret `<service>-secrets` |
| `LLM_MODEL_*` tag 覆盖 | 本地 `.env` | K8s ConfigMap `<service>-config` |
| `local` tag 可用性 | **可用**（本地跑 Ollama） | **不可用**（集群内无 Ollama） |

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
# 复制为 .env 后填入真实值
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
├── config/
│   └── config.yaml              # 开发/生产共用模型定义（提交 git）
│
├── python/
│   ├── llm_client.py            # 核心 client + tag 路由
│   ├── session.py               # 多轮会话（阶段二）
│   ├── structured.py            # 结构化输出（阶段二）
│   ├── templates.py             # Prompt 模板管理（阶段二）
│   └── tests/
│       ├── test_client.py
│       └── test_session.py
│
├── typescript/
│   ├── llm_client.ts
│   ├── session.ts               # 阶段二
│   ├── structured.ts            # 阶段二
│   └── tests/
│       └── llm_client.test.ts
│
├── go/
│   ├── llm_client.go
│   ├── session.go               # 阶段二
│   └── llm_client_test.go
│
├── k8s/
│   ├── kustomization.yaml       # 统一入口
│   └── litellm/
│       ├── namespace.yaml
│       ├── configmap.yaml       # 嵌入 config.yaml 内容（提交 git）
│       ├── secret.yaml.example  # Secret 模板（提交 git，真实值不提交）
│       ├── deployment.yaml
│       ├── service.yaml
│       └── hpa.yaml
│
├── .env.example                 # 开发环境变量模板（提交 git）
├── .env                         # 真实密钥（.gitignore）
├── .gitignore
└── README.md
```

`.gitignore` 必须包含：

```
.env
k8s/litellm/secret.yaml
```

---

## 六、Kubernetes 生产部署

### 6.1 集群拓扑

```
Kubernetes Cluster
│
├── namespace: llm-system
│   ├── Deployment: litellm-proxy (replicas: 2，反亲和性，不同节点)
│   │   └── 健康检查：startupProbe / livenessProbe / readinessProbe
│   ├── Service: litellm-proxy (ClusterIP)
│   │   └── 集群内 DNS：litellm-proxy.llm-system:4000
│   ├── ConfigMap: litellm-config  ← 挂载 config.yaml
│   ├── Secret: litellm-secrets    ← 厂商 API Keys + LITELLM_MASTER_KEY
│   └── HPA: min=2 max=6 cpu=60%
│
└── namespace: apps
    ├── python-agent  → ConfigMap(非敏感) + Secret(LLM_API_KEY)
    ├── nodejs-tool   → ConfigMap(非敏感) + Secret(LLM_API_KEY)
    └── go-service    → ConfigMap(非敏感) + Secret(LLM_API_KEY)

全部业务服务 → http://litellm-proxy.llm-system:4000（集群内，不过公网）
```

### 6.2 namespace.yaml

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: llm-system
  labels:
    app.kubernetes.io/name: llm-system
```

### 6.3 configmap.yaml

`config.yaml` 内容嵌入 ConfigMap，**改模型配置无需重建镜像**，触发滚动重启即可。内容与 `config/config.yaml` 保持一致，**生产版 fallback 链去掉 `local-chat`**。

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: litellm-config
  namespace: llm-system
data:
  config.yaml: |
    model_list:
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

    router_settings:
      routing_strategy: simple-shuffle
      num_retries: 2
      timeout: 30
      retry_after: 3
      fallbacks:
        - auto-chat:   [gpt-chat]    # 生产无 local-chat
        - auto-vision: [gpt-vision]
        - gemini-chat: [gpt-chat]

    general_settings:
      master_key: os.environ/LITELLM_MASTER_KEY
      rpm_limit: 500
      tpm_limit: 1000000
      request_timeout: 60
      default_fallbacks: [gpt-chat]
```

### 6.4 secret.yaml.example（模板，提交 git）

```yaml
# secret.yaml.example
# 真实 secret.yaml 不提交 git
# 创建方式见下方 kubectl 命令
apiVersion: v1
kind: Secret
metadata:
  name: litellm-secrets
  namespace: llm-system
type: Opaque
stringData:
  ANTHROPIC_API_KEY: ""
  OPENAI_API_KEY: ""
  GEMINI_API_KEY: ""
  LITELLM_MASTER_KEY: ""
```

```bash
# 手动创建（不进 git）
kubectl create secret generic litellm-secrets \
  --namespace llm-system \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-... \
  --from-literal=OPENAI_API_KEY=sk-... \
  --from-literal=GEMINI_API_KEY=AI... \
  --from-literal=LITELLM_MASTER_KEY=sk-litellm-...
```

### 6.5 deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm-proxy
  namespace: llm-system
  labels:
    app: litellm-proxy
spec:
  replicas: 2
  selector:
    matchLabels:
      app: litellm-proxy
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0     # 滚动更新全程保证有副本可用
      maxSurge: 1
  template:
    metadata:
      labels:
        app: litellm-proxy
    spec:
      containers:
        - name: litellm
          image: ghcr.io/berriai/litellm:main-latest
          imagePullPolicy: Always
          ports:
            - containerPort: 4000
              name: http
          args:
            - "--config"
            - "/app/config/config.yaml"
            - "--port"
            - "4000"

          # 厂商 API Keys 从 Secret 注入
          envFrom:
            - secretRef:
                name: litellm-secrets

          # ── 健康检查三件套 ─────────────────────────────────────────

          # startupProbe：冷启动探针，最多等 60s（6次×10s）
          # 通过后由 liveness/readiness 接管，期间不触发重启
          startupProbe:
            httpGet:
              path: /health/liveliness
              port: 4000
            failureThreshold: 6
            periodSeconds: 10

          # livenessProbe：进程存活探针
          # 连续 3 次失败 → kubelet 重启 Pod
          # 检测：进程死锁、内存泄漏导致无响应
          livenessProbe:
            httpGet:
              path: /health/liveliness
              port: 4000
            periodSeconds: 15
            timeoutSeconds: 5
            failureThreshold: 3

          # readinessProbe：流量就绪探针
          # 失败 → 从 Service Endpoints 摘除，不重启
          # 恢复 → 自动重新加入 Endpoints
          # 检测：模型 API 连通性（如限流时摘除该 Pod）
          readinessProbe:
            httpGet:
              path: /health/readiness
              port: 4000
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 2
            successThreshold: 1

          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "1Gi"

          volumeMounts:
            - name: config-volume
              mountPath: /app/config
              readOnly: true

      volumes:
        - name: config-volume
          configMap:
            name: litellm-config

      # 两副本不调度到同一节点
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchLabels:
                    app: litellm-proxy
                topologyKey: kubernetes.io/hostname
```

### 6.6 service.yaml

```yaml
apiVersion: v1
kind: Service
metadata:
  name: litellm-proxy
  namespace: llm-system
  labels:
    app: litellm-proxy
spec:
  type: ClusterIP           # 仅集群内可达，不暴露公网
  selector:
    app: litellm-proxy
  ports:
    - name: http
      port: 4000
      targetPort: 4000
      protocol: TCP
```

集群内访问地址：
- 完整：`http://litellm-proxy.llm-system.svc.cluster.local:4000`
- 简写：`http://litellm-proxy.llm-system:4000`

### 6.7 hpa.yaml

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: litellm-proxy-hpa
  namespace: llm-system
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: litellm-proxy
  minReplicas: 2
  maxReplicas: 6
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60    # 扩容前观察 60s，防抖
    scaleDown:
      stabilizationWindowSeconds: 300   # 缩容前观察 5min，防频繁缩
```

### 6.8 kustomization.yaml

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: llm-system
resources:
  - litellm/namespace.yaml
  - litellm/configmap.yaml
  - litellm/deployment.yaml
  - litellm/service.yaml
  - litellm/hpa.yaml
  # secret.yaml 不在此列表，通过 kubectl create secret 或外部工具管理
```

### 6.9 业务服务的 K8s 配置

每个业务服务维护自己的 ConfigMap（非敏感）和 Secret（`LLM_API_KEY`），职责分离。

```yaml
# <service>-config ConfigMap（非敏感，提交 git）
apiVersion: v1
kind: ConfigMap
metadata:
  name: python-agent-config
  namespace: apps
data:
  LLM_BASE_URL: "http://litellm-proxy.llm-system:4000"
  LLM_MODEL_CHAT: "auto-chat"
  LLM_MODEL_VISION: "auto-vision"
  LLM_MODEL_VIDEO: "gemini-vision"
  LLM_MODEL_EMBEDDING: "text-embedding"
  LLM_MODEL_IMAGE_GEN: "gpt-image-gen"
  LLM_MODEL_FAST: "gemini-chat"
  # LLM_MODEL_LOCAL 不配置：生产无 Ollama，禁止使用 local tag
```

```yaml
# <service>-secrets Secret（不提交 git）
apiVersion: v1
kind: Secret
metadata:
  name: python-agent-secrets
  namespace: apps
type: Opaque
stringData:
  LLM_API_KEY: "sk-litellm-..."    # 与 LITELLM_MASTER_KEY 值相同
```

### 6.10 运维操作速查

```bash
# 首次部署
kubectl apply -k k8s/

# 仅更新 config.yaml（改模型配置，无需重建镜像）
kubectl apply -f k8s/litellm/configmap.yaml
kubectl rollout restart deployment/litellm-proxy -n llm-system
kubectl rollout status deployment/litellm-proxy -n llm-system

# 更新 LiteLLM 版本（改 deployment.yaml 的 image tag）
kubectl apply -f k8s/litellm/deployment.yaml
kubectl rollout status deployment/litellm-proxy -n llm-system
kubectl rollout undo deployment/litellm-proxy -n llm-system   # 回滚

# 日常查看
kubectl get pods -n llm-system
kubectl get hpa  -n llm-system
kubectl logs -l app=litellm-proxy -n llm-system --follow
kubectl describe pod -l app=litellm-proxy -n llm-system       # 查健康检查详情
```

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
- [x] 开发 `.env` + 生产 K8s 双环境配置体系
- [x] K8s Deployment + Service + ConfigMap + Secret + HPA + 健康检查三件套

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
模型定义本身与环境无关，差异只在两处：API Keys（通过环境变量注入，两套环境各自维护）和 fallback 链（生产的 ConfigMap 中去掉 `local-chat`）。共用一份文件减少维护分叉；K8s ConfigMap 嵌入内容时手动同步（或 CI 自动同步）。

**`local` tag 为什么在生产中不可用？**
Ollama 运行在开发者本机，不在 K8s 集群内。生产 K8s ConfigMap 不配置 `LLM_MODEL_LOCAL`，业务服务若在生产调用 `local` capability，SDK 层仍会映射到默认的 `local-chat`，Proxy 会因为 `local-chat` model 的 `base_url`（localhost:11434）在集群内不可达而报错——这是有意为之的硬约束，防止隐私数据意外路由到公网模型。

**业务服务的 `LLM_API_KEY` 为什么放 Secret 而不是 ConfigMap？**
`LLM_API_KEY` 是访问 Proxy 的凭证（与 `LITELLM_MASTER_KEY` 值相同），属于敏感信息。ConfigMap 不加密，`kubectl get configmap -o yaml` 可明文读取。非敏感的 `LLM_BASE_URL` 和 `LLM_MODEL_*` 放 ConfigMap，敏感的 `LLM_API_KEY` 放 Secret，职责分离。

**config.yaml 和 K8s ConfigMap 如何保持同步？**
两者内容基本相同，差异只有 fallback 链（生产去掉 `local-chat`）。推荐做法：CI 流水线中用脚本从 `config/config.yaml` 生成 K8s ConfigMap，自动应用差异，避免手动维护两份文件产生漂移。

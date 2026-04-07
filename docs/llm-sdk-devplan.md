# LLM 内部 SDK 开发计划

> 配套文档：llm-sdk-design.md
> 原则：每个任务交付时，三语言（Python / TypeScript / Go）同步完成，不留「先做一个语言后补」的缺口。

---

## 总览

| 阶段 | 主题 | 状态 | 核心交付 |
|------|------|------|---------|
| 阶段一 | 基础骨架 | ✅ 已完成 | 三语言 client + K8s 全套部署 |
| 阶段二 | 增强能力 | 🔵 下一步 | 结构化输出 + Session + 流式 + 模板 + 错误处理 |
| 阶段三 | 效率与可观测性 | ⏳ 阶段二后 | 缓存 + Tool use + 统计 + 集成测试 |
| 阶段四 | 成熟与治理 | 📋 中长期 | Langfuse + 审计日志 + A/B 评估 + 多集群 |

---

## 阶段一：基础骨架（已完成）

### L3 路由层
- [x] `config.yaml` 完整模型配置（7 个 capability tag，fallback 链，厂商别名）
- [x] Kubernetes 全套 Manifest（Deployment / Service / ConfigMap / Secret / HPA）
- [x] 健康检查三件套（startupProbe / livenessProbe / readinessProbe）
- [x] 开发 `.env` ↔ 生产 K8s 双环境配置体系

### L2 SDK 层
- [x] `llm_client.py`：`chat` / `embed` / `image_gen`，capability tag 路由，vision 自动推断
- [x] `llm_client.ts`：TypeScript 类型安全，overload 签名
- [x] `llm_client.go`：零外部依赖，标准库 `net/http`

---

## 阶段二：增强能力（下一步开发）

> 开发顺序按优先级排列，同优先级内任务可并行。

### 优先级 1 — 最高频，优先交付

#### 任务 2-1：结构化输出（`chat_structured`）

**交付物：**
- `sdk/python/llm_sdk/structured.py`：接受 Pydantic BaseModel，返回强类型实例
- `sdk/typescript/structured.ts`：接受 Zod schema，返回推断类型
- `sdk/go/structured.go`：接受 struct 指针，通过反射生成 JSON Schema，解析结果

**接口契约：**
```python
# Python
result: Product = client.chat_structured(prompt, schema=Product)

# TypeScript
const result: Product = await client.chatStructured(prompt, { schema: ProductSchema })

# Go
var result Product
err := c.ChatStructured(ctx, prompt, &result, nil)
```

**实现要点：**
1. SDK 层将 schema 转为 JSON Schema 字符串
2. 注入 system prompt：`请严格按照以下 JSON Schema 返回结果，只返回 JSON，不要有任何其他内容：{schema}`
3. 调用 `chat()`，拿到响应字符串
4. 解析 JSON，填充强类型对象
5. 解析失败时抛出 `StructuredOutputError`，携带原始响应便于调试

---

#### 任务 2-2：多轮会话 Session 对象

**交付物：**
- `sdk/python/llm_sdk/session.py`
- `sdk/typescript/session.ts`
- `sdk/go/session.go`

**接口契约：**
```python
# Python
session = client.session(system="你是代码审查助手")
r1 = session.chat("审查这段代码：...")
r2 = session.chat("给出修复方案")       # history 自动传递
r3 = session.chat_structured("...", schema=ReviewResult)
session.clear()                         # 清空 history

# TypeScript
const session = client.session({ system: '...' })
const r1 = await session.chat('...')

// Go
sess := c.NewSession(&llmclient.SessionOpts{System: "..."})
r1, _ := sess.Chat(ctx, "...", nil)
```

**实现要点：**
1. Session 对象内部维护 `messages []Message` 列表
2. 每次 `chat()` 调用将用户消息追加到 history，将模型回复也追加
3. `clear()` 重置 history 但保留 system prompt
4. history 过长时（超过阈值 token 数）截断最早的非 system 消息，保留最近 N 轮
5. Session 不跨请求持久化，生命周期与对象绑定

---

### 优先级 2 — 体验提升

#### 任务 2-3：流式输出（`chat_stream`）

**交付物：** 三语言 client 各新增 `chat_stream` 方法

**接口契约：**
```python
# Python
async for chunk in client.chat_stream("写一篇文章"):
    print(chunk, end="", flush=True)

# TypeScript
for await (const chunk of client.chatStream('写一篇文章')) {
  process.stdout.write(chunk)
}

# Go
stream, _ := c.ChatStream(ctx, "写一篇文章", nil)
for chunk := range stream {
    fmt.Print(chunk)
}
```

**实现要点：**
1. 向 Proxy 发送 `stream: true` 参数
2. 解析 SSE（Server-Sent Events）格式响应，逐块 yield delta 文本
3. 三语言底层 streaming 处理有差异，统一暴露为 async generator / channel
4. Session 也支持 `chat_stream`，流结束后将完整回复追加到 history

---

#### 任务 2-4：Prompt 模板管理器

**交付物：**
- `sdk/python/llm_sdk/templates.py`
- `sdk/typescript/templates.ts`
- `sdk/go/templates.go`
- `sdk/prompts/` 目录约定（`.txt` 模板文件）

**接口契约：**
```python
# Python — 文件加载
client.load_templates("../prompts")        # 扫描目录，注册所有 .txt

# 或代码注册
client.register_template("code_review", """
你是一个资深 {language} 工程师。
审查以下代码，关注：{focus}
""")

reply = client.chat_with_template(
    "code_review",
    user_prompt=code,
    language="Python",
    focus="内存泄漏、SQL 注入"
)
```

**实现要点：**
1. 模板变量用 `{var_name}` 占位，渲染时做字符串替换
2. 模板分 system 段和 user 段，用 `---` 分隔（可选）
3. 未找到模板时抛出 `TemplateNotFoundError`
4. 支持热加载（重新调用 `load_templates` 更新注册表）

---

### 优先级 3 — 稳定性

#### 任务 2-5：错误分类与差异化重试

**交付物：** 三语言 client 错误处理升级

**错误分类：**

| 错误类型 | HTTP 状态 | 处理策略 |
|---------|---------|---------|
| 限流（RateLimitError） | 429 | 指数退避重试，读取 `Retry-After` 头 |
| 超时（TimeoutError） | 408 / 504 | 立即重试一次，失败则抛出 |
| 模型错误（ModelError） | 400 / 422 | 不重试，直接抛出，携带原始错误信息 |
| 服务不可用（ProxyError） | 500 / 503 | 重试 2 次，指数退避 |
| 网络错误（NetworkError） | — | 重试 2 次 |
| 认证错误（AuthError） | 401 / 403 | 不重试，直接抛出 |

**实现要点：**
1. 所有错误继承自 `LLMError` 基类
2. 重试逻辑封装在 client 内，业务层不需要处理
3. 最大重试次数和退避参数可配置（通过 `LLMClient` 构造参数）
4. 超过重试次数后抛出最后一次的原始错误

---

## 阶段三：效率与可观测性（阶段二完成后）

### 任务 3-1：请求级缓存

**适用语言：** Python / TypeScript（Go 可选）

**设计：**
- 缓存 key = `hash(model_name + messages_json)`
- 默认内存缓存（`TTLCache`），可选 Redis 后端
- 仅对非流式、非结构化调用缓存
- `LLMClient` 构造时传入 `cache=True` 或 `cache=RedisCache(url=...)`
- 命中缓存时在响应中附加 `_cached: True` 标记

---

### 任务 3-2：Tool use / Function calling 封装

**交付物：** 三语言新增 `chat_with_tools` 方法

**接口契约：**
```python
# Python
@llm_tool
def get_weather(city: str) -> str:
    """获取指定城市的天气"""
    return weather_api.fetch(city)

reply = client.chat_with_tools(
    "北京今天天气怎么样？",
    tools=[get_weather]
)
# SDK 自动处理 tool_call → 执行函数 → 把结果回传模型 → 返回最终回复
```

**实现要点：**
1. `@llm_tool` 装饰器从函数签名和 docstring 自动生成 tool schema
2. SDK 自动处理 tool_call 循环（模型调用 tool → 执行 → 回传结果 → 继续对话）
3. 最大循环次数可配置，防止无限循环

---

### 任务 3-3：Token 用量统计

**设计：**
- LiteLLM Proxy 原生支持 Prometheus metrics，开启 `/metrics` 端点
- K8s 部署中添加 Prometheus ServiceMonitor
- 关键指标：`litellm_requests_total`（按 model、status）、`litellm_tokens_total`（按 model、type）、`litellm_request_duration_seconds`

**K8s 配置新增：**
```yaml
# deployment.yaml 新增端口
- containerPort: 9090
  name: metrics

# ServiceMonitor（需要 Prometheus Operator）
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: litellm-proxy
  namespace: llm-system
spec:
  selector:
    matchLabels:
      app: litellm-proxy
  endpoints:
    - port: metrics
      path: /metrics
      interval: 30s
```

---

### 任务 3-4：三语言统一集成测试套件

**目标：** 用同一份测试用例描述，在三个语言的 client 上都跑，验证行为一致。

**测试覆盖：**
- 基础 chat / embed / image_gen
- capability tag 正确路由到 model_name
- vision 自动推断
- 错误分类（mock 429、500 等）
- Session history 维护正确性
- 结构化输出解析正确性

**运行方式：**
```bash
# 需要本地 Proxy 在 localhost:4000 运行
pytest sdk/compat-tests/test_python_sdk.py -v
npx vitest run sdk/typescript/tests/sdk.test.ts
go test ./sdk/go/... -v
```

---

## 阶段四：成熟与治理（中长期）

### 任务 4-1：Langfuse 可观测性接入

在 `config.yaml` 的 `litellm_settings` 中添加：
```yaml
litellm_settings:
  success_callback: ["langfuse"]
  failure_callback: ["langfuse"]
```

K8s Secret 中新增：
```
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
```

功能：每次请求自动上报 prompt、completion、token 用量、延迟、模型名到 Langfuse 控制台。

---

### 任务 4-2：请求审计日志持久化

`config.yaml` 新增：
```yaml
general_settings:
  database_url: os.environ/DATABASE_URL    # PostgreSQL 连接串
```

K8s 中新增 PostgreSQL（或使用云托管数据库），Secret 中添加 `DATABASE_URL`。

---

### 任务 4-3：模型 A/B 评估框架

对同一批 prompt，分别调用两个不同 model_name，对比：
- 延迟（p50 / p95）
- Token 用量
- 人工评分 / 自动评分（用另一个 LLM 打分）

交付为 Python 脚本工具，不耦合到 SDK 主体代码。

---

### 任务 4-4：多集群 / 跨地域 Proxy 高可用

在多个 K8s 集群各部署一套 `llm-system`，业务侧通过全局负载均衡（如 Cloudflare / AWS Route53）路由到最近节点。各集群 Proxy 配置相同，Secret 独立维护。

---

## 开发约定

### 每个任务的 DoD（完成定义）

1. **三语言同步交付**：Python / TypeScript / Go 三端同时完成，接口语义一致
2. **测试覆盖**：每个新功能附带单元测试，关键路径有集成测试
3. **文档同步**：`llm-sdk-design.md` 中对应接口契约更新
4. **向后兼容**：现有调用方式不受影响，新功能通过可选参数扩展

### 版本约定

```
v0.1.0  阶段一完成（当前）
v0.2.0  结构化输出 + Session（任务 2-1 / 2-2）
v0.3.0  流式输出 + 模板 + 错误处理（任务 2-3 / 2-4 / 2-5）
v0.4.0  阶段三全部（缓存 / Tool use / 统计 / 集成测试）
v1.0.0  阶段四核心（Langfuse + 审计日志）
```

### 文件变更对照表

| 任务 | Python | TypeScript | Go | 配置/K8s |
|------|--------|------------|-----|---------|
| 2-1 结构化输出 | `structured.py` | `structured.ts` | `structured.go` | — |
| 2-2 Session | `session.py` | `session.ts` | `session.go` | — |
| 2-3 流式 | `llm_client.py` | `llm_client.ts` | `llm_client.go` | — |
| 2-4 模板 | `templates.py` | `templates.ts` | `templates.go` | `sdk/prompts/` |
| 2-5 错误处理 | `llm_client.py` | `llm_client.ts` | `llm_client.go` | — |
| 3-1 缓存 | `llm_client.py` | `llm_client.ts` | — | — |
| 3-2 Tool use | `llm_client.py` | `llm_client.ts` | `llm_client.go` | — |
| 3-3 统计 | — | — | — | `proxy/k8s/litellm/` |
| 3-4 集成测试 | `sdk/compat-tests/` | `sdk/compat-tests/` | `sdk/compat-tests/` | — |
| 4-1 Langfuse | — | — | — | `proxy/config/config.yaml` + `secret` |
| 4-2 审计日志 | — | — | — | `proxy/config/config.yaml` + `secret` + PG |

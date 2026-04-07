# Changelog

All notable changes to the LLM SDK project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-04

### Added

- Langfuse callback 配置与 PostgreSQL 审计日志入口
- Proxy K8s NetworkPolicy 与 SealedSecret 模板
- ConfigMap 生成脚本 `scripts/generate_k8s_configmap.py`
- 统一 compat 验证脚本 `scripts/test_compat.py` 与 `scripts/test-compat.ps1`
- GitHub Actions CI 与 release 工作流
- Proxy 部署、监控、回滚、升级文档

### Changed

- Python 与 TypeScript 包版本提升到 1.0.0
- TypeScript compat tests 增加独立类型检查入口
- Proxy K8s ConfigMap 与源码配置保持同步

### Fixed

- 兼容测试入口分散、跨目录 TypeScript 文件编译报错
- Proxy K8s Secret 模板缺少 SiliconFlow、Langfuse、DATABASE_URL 字段

---

## [0.3.0] - 2026-03-31

### Added

#### Phase 3: Efficiency & Observability

- **Request-level Caching** (Python, TypeScript, Go)
  - Memory-based TTLCache with configurable TTL (default: 1 hour)
  - Optional Redis backend support
  - Cache key based on `hash(model_name + messages_json)`
  - Response includes `_cached: true` marker when cache hit
  - Only applies to non-streaming, non-structured calls

- **Tool Use / Function Calling** (Python, TypeScript, Go)
  - Python: `@llm_tool` decorator + `chat_with_tools()` method
  - TypeScript: `llmTool()` decorator + `chatWithTools()` method
  - Go: `Tool` interface + `ChatWithTools()` method
  - Automatic tool call loop: LLM requests → execute function → return result
  - JSON Schema generation from type signatures

- **Prometheus Metrics** (Kubernetes)
  - Added `/metrics` endpoint on port 9090
  - ServiceMonitor for Prometheus Operator integration
  - Key metrics exposed:
    - `litellm_requests_total` (by model, status)
    - `litellm_tokens_total` (by model, type: prompt/completion)
    - `litellm_request_duration_seconds` (latency histogram)

- **Integration Test Suite** (All Languages)
  - Created `sdk/compat-tests/` directory
  - Python: `pytest sdk/compat-tests/test_python_sdk.py -v`
  - TypeScript: compat tests located in `sdk/compat-tests/typescript-sdk.test.ts`
  - Go: compatibility coverage kept under `sdk/compat-tests/`
  - Test coverage:
    - Basic chat / embed / image_gen
    - Capability tag routing
    - Vision auto-inference
    - Error classification (429, 401, 500)
    - Session history
    - Structured output parsing
    - Cache hit/miss
    - Tool use complete flow

### Changed

- Updated version from 0.2.0 to 0.3.0 (Python, TypeScript)
- Enhanced K8s deployment with metrics support
- Updated AGENTS.md documentation for all components

### Fixed

- N/A (initial Phase 3 release)

---

## [0.2.0] - 2026-03-29

### Added

#### Phase 2: Core Features

- **Python SDK** (Pydantic-based)
  - `LLMClient` with capability-based routing
  - Session management with history
  - Structured output with Pydantic models
  - Streaming support
  - Template registry
  - Error hierarchy (8 types)

- **TypeScript SDK** (Zod-based)
  - `LLMClient` with identical interface
  - Session management
  - Structured output with Zod schemas
  - Streaming with async iterators
  - Template registry

- **Go SDK** (stdlib only)
  - `Client` with zero external dependencies
  - Session management
  - Structured output with struct tags
  - Streaming with channels
  - Template registry

- **LiteLLM Proxy Configuration**
  - Model definitions for 7 capability tags
  - Fallback chains for production reliability
  - Rate limiting and retry policies

- **Kubernetes Deployment**
  - Kustomize-based manifests
  - HPA for auto-scaling (2-6 replicas)
  - Health checks and pod anti-affinity
  - Secret management template

---

## [0.1.0] - 2026-03-28

### Added

- Initial project setup
- Architecture documentation
- Development plan (Phase 1-4)
- Project structure (`sdk/`, `proxy/`)

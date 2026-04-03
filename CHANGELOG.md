# Changelog

All notable changes to the LLM SDK project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  - Created `tests/integration/` directory
  - Python: `pytest tests/integration/test_python_sdk.py -v`
  - TypeScript: `npx vitest run tests/integration/typescript-sdk.test.ts`
  - Go: `go test ./tests/integration/...`
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
- Project structure (python/, typescript/, go/, k8s/, config/)

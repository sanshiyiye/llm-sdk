# LLM SDK - Project Knowledge Base

**Updated:** 2026-04-13  
**Project:** Multi-language LLM Internal SDK (Python / TypeScript / Go)

---

## OVERVIEW

Unified SDK providing identical interfaces across Python, TypeScript, and Go for accessing LLM models (Anthropic, OpenAI, Gemini, Ollama) through a LiteLLM Proxy layer. Business code uses capability tags (`chat`, `vision`, `fast`) rather than hardcoded model names.

### Product Positioning

| Layer | Role |
|-------|------|
| **L1 Business** | Only knows SDK API + capability tags |
| **L2 SDK** | Capability routing, retry, error normalization |
| **L3 LiteLLM Proxy** | Model registry, provider keys, fallback, rate limiting |
| **L4 Providers** | Anthropic, OpenAI, Gemini, Ollama, etc. |

**Default Mode: Shared-Proxy-First**
- Teams connect to a centrally-managed Proxy instance
- Business code only needs `LLM_BASE_URL` + `LLM_API_KEY`
- No knowledge of provider keys, routing, or model names required

**Local Dev Mode (optional)**
- Use `docker-compose.dev.yaml` to spin up a local Proxy
- Run `python proxy/start_proxy.py` after setting up `.env`
- Same SDK code works for both modes

### Minimum Required Configuration

```bash
LLM_BASE_URL=https://your-proxy.example.com   # Shared Proxy URL (from platform team)
LLM_API_KEY=sk-your-team-key                  # Team API key (from platform team)
```

That's it. Everything else is optional.

---

## STRUCTURE

```
llm-sdk/
├── sdk/
│   ├── python/      # Python SDK (Pydantic-based)
│   ├── typescript/  # TypeScript SDK (Zod-based)
│   ├── go/          # Go SDK (stdlib only)
│   ├── prompts/     # Shared prompt templates
│   ├── examples/    # SDK examples
│   └── compat-tests/# SDK/Proxy compatibility tests
├── proxy/
│   ├── config/      # LiteLLM Proxy configuration
│   ├── k8s/         # Kubernetes deployment manifests
│   ├── docker-compose.dev.yaml  # Local dev one-command startup
│   ├── .env.example # Environment template
│   └── start_proxy.py
├── starters/        # Per-language starter templates for new projects
│   ├── python/
│   ├── typescript/
│   └── go/
├── docs/            # Design documentation
└── README.md        # Quick start guide (3-minute onboarding)
```

---

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| **Add SDK feature** | `sdk/python/`, `sdk/typescript/`, `sdk/go/` | Must implement in all 3 languages |
| **Update model config** | `proxy/config/config.yaml` | LiteLLM Proxy model registry |
| **Deploy to production** | `proxy/k8s/` | Kustomize + K8s manifests |
| **Add prompt template** | `sdk/prompts/*.txt` | Shared across all languages |
| **Environment setup** | `proxy/.env.example` | Copy to `proxy/.env`, fill API keys |
| **Architecture docs** | `docs/llm-sdk-design.md` | System design decisions |
| **New project onboarding** | `starters/` | Per-language starter templates |
| **Diagnose connection issues** | `client.doctor()` (Python/TS) / `client.Doctor()` (Go) | Returns structured health check results |
| **Local dev startup** | `proxy/docker-compose.dev.yaml` | One-command local Proxy |

---

## CODE MAP

### Core APIs (All Languages)

| Method | Purpose | Notes |
|--------|---------|-------|
| `chat(prompt, opts?)` | Basic chat | Returns `{content, _cached}` |
| `chat_stream(prompt, opts?)` | Streaming | Iterator/AsyncGenerator/channel |
| `embed(text)` | Text vectorization | Returns float[] |
| `image_gen(prompt, opts?)` | Image generation | Returns URL string |
| `session(system?)` | Multi-turn | Returns Session object |
| `chat_structured(prompt, schema)` | Structured output | Pydantic/Zod/Go struct |
| `doctor()` | Health check & diagnostics | Returns DoctorResult |

### Capability Tags (7 tags)

| Tag | Default Model | Use Case | Production |
|-----|---------------|----------|------------|
| `chat` | auto-chat | General conversation | ✓ |
| `vision` | auto-vision | Image understanding | ✓ |
| `video-input` | gemini-vision | Video frame analysis | ✓ |
| `embedding` | text-embedding | Text vectorization | ✓ |
| `image-gen` | gpt-image-gen | Image generation | ✓ |
| `fast` | gemini-chat | Latency-sensitive | ✓ |
| `local` | local-chat | Local/Ollama | **Dev only** |

Override via env vars: `LLM_MODEL_CHAT`, `LLM_MODEL_VISION`, etc.

### Doctor / Health Check

```python
# Python
result = client.doctor()
result.ok          # bool
result.checks      # list of DoctorCheck(name, ok, message, fix)
result.print()     # human-readable output with fix hints
```

```typescript
// TypeScript
const result = await client.doctor()
result.ok          // boolean
result.checks      // DoctorCheck[]
result.print()     // human-readable output
```

```go
// Go
result := c.Doctor(ctx)
result.OK          // bool
result.Checks      // []DoctorCheck
result.Print()     // human-readable output
```

---

## CONVENTIONS

### Architecture Principles

1. **Layer Separation**: L1 (Business) → L2 (SDK) → L3 (LiteLLM Proxy) → L4 (Providers)
2. **Capability-based routing**: Always use tags (`chat`, `vision`), never hardcode model names
3. **Three-language parity**: Features must be implemented in Python/TypeScript/Go simultaneously
4. **Proxy-only access**: No direct provider API calls from business layer
5. **Shared-proxy-first**: Default onboarding path is connecting to a shared Proxy instance
6. **Self-diagnosing**: SDK can always explain what's wrong and how to fix it

### Environment Variables

```bash
# Minimum required (shared proxy mode)
LLM_BASE_URL=https://your-proxy.example.com
LLM_API_KEY=sk-your-team-key

# Optional: capability overrides (advanced)
LLM_MODEL_CHAT=auto-chat
LLM_MODEL_VISION=auto-vision
LLM_MODEL_VIDEO=gemini-vision
LLM_MODEL_EMBEDDING=text-embedding
LLM_MODEL_IMAGE_GEN=gpt-image-gen
LLM_MODEL_FAST=gemini-chat
LLM_MODEL_REASONING=auto-reasoning
LLM_MODEL_LOCAL=local-chat
```

### Configuration Boundaries

| Concern | Owner | Where |
|---------|-------|-------|
| Provider API keys | Platform team | LiteLLM Proxy env / K8s Secret |
| Model routing & fallback | Platform team | `proxy/config/config.yaml` |
| Rate limiting & quotas | Platform team | LiteLLM Proxy config |
| Audit logging | Platform team | PostgreSQL / Langfuse |
| Proxy URL & team key | Platform team → Business team | Shared out-of-band |
| Capability tag overrides | Business team (optional) | `.env` per project |

### Testing

```bash
# Python
cd sdk/python && pytest tests/ -v

# TypeScript
cd sdk/typescript && npm test

# Go
cd sdk/go && go test ./... -v

# Compat tests (all languages, requires running Proxy)
cd sdk/python && pytest ../compat-tests/test_python_sdk.py -v
cd sdk/typescript && npm run test:compat
cd sdk/compat-tests && go test -v
```

---

## ANTI-PATTERNS

| Pattern | Why Forbidden | Correct Approach |
|---------|---------------|------------------|
| Hardcode model names | Breaks capability routing | Use `capability="chat"` tag |
| Use `local` tag in prod | Ollama unreachable in production | Use `chat` or `fast` tag |
| Store `.env` in git | Security risk | Listed in `.gitignore` |
| Direct provider API calls | Bypasses Proxy fallback/routing | Always use SDK → Proxy |
| Implement in 1 language only | Breaks parity | All 3 languages together |
| Retry on Auth/Model errors | Will never succeed | Only retry RateLimit/Network errors |
| Expose provider keys to business layer | Security risk | Platform team manages keys in Proxy |
| Ask new users to configure Proxy | Increases onboarding friction | Use shared Proxy by default |

---

## QUICK START

### Path A: Shared Proxy (default, recommended)

```bash
# Python
pip install llm-sdk
export LLM_BASE_URL=https://your-proxy.example.com
export LLM_API_KEY=sk-your-team-key
python -c "from llm_sdk import client; print(client.chat('Hello')['content'])"
```

Get `LLM_BASE_URL` and `LLM_API_KEY` from your platform team.

### Path B: Local Dev Proxy

```bash
# One-command startup
cp proxy/.env.example proxy/.env   # Fill in provider API keys
docker compose -f proxy/docker-compose.dev.yaml up -d

# Wait for readiness
curl http://localhost:4000/health/readiness

# Then use SDK (same code as Path A)
export LLM_BASE_URL=http://localhost:4000
export LLM_API_KEY=sk-local-dev
```

### Diagnose Issues

```python
from llm_sdk import client
result = client.doctor()
result.print()
```

---

## NOTES

- Go SDK uses zero external dependencies (stdlib only)
- Python SDK requires Pydantic v2
- TypeScript SDK uses Zod for schema validation
- All SDKs share the same `sdk/prompts/` directory for templates
- K8s deployment uses Kustomize with HPA auto-scaling (2-6 replicas)
- `doctor()` checks: URL reachability, auth validity, capability override sanity

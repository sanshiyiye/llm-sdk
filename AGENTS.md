# LLM SDK - Project Knowledge Base

**Generated:** 2026-03-31  
**Project:** Multi-language LLM Internal SDK (Python / TypeScript / Go)

---

## OVERVIEW

Unified SDK providing identical interfaces across Python, TypeScript, and Go for accessing LLM models (Anthropic, OpenAI, Gemini, Ollama) through a LiteLLM Proxy layer. Business code uses capability tags (`chat`, `vision`, `fast`) rather than hardcoded model names.

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
│   ├── .env.example # Environment template
│   └── start_proxy.py
├── docs/            # Design documentation
└── README.md        # Quick start guide
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

---

## CODE MAP

### Core APIs (All Languages)

| Method | Purpose | Notes |
|--------|---------|-------|
| `chat(prompt, opts?)` | Basic chat | Returns string |
| `chat_stream(prompt, opts?)` | Streaming | Iterator/AsyncGenerator/channel |
| `embed(text)` | Text vectorization | Returns float[] |
| `image_gen(prompt, opts?)` | Image generation | Returns URL string |
| `session(system?)` | Multi-turn | Returns Session object |
| `chat_structured(prompt, schema)` | Structured output | Pydantic/Zod/Go struct |

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

---

## CONVENTIONS

### Architecture Principles
1. **Layer Separation**: L1 (Business) → L2 (SDK) → L3 (LiteLLM Proxy) → L4 (Providers)
2. **Capability-based routing**: Always use tags (`chat`, `vision`), never hardcode model names
3. **Three-language parity**: Features must be implemented in Python/TypeScript/Go simultaneously
4. **Proxy-only access**: No direct provider API calls from business layer

### Environment Variables
```bash
LLM_BASE_URL=http://localhost:4000    # Proxy URL
LLM_API_KEY=no-key                    # Proxy API key
LLM_MODEL_CHAT=auto-chat              # Override capability tag
LLM_MODEL_VISION=auto-vision
# ... etc for all 7 tags
```

### Testing
```bash
# Python
cd sdk/python && pytest tests/ -v

# TypeScript
cd sdk/typescript && npm test

# Go
cd sdk/go && go test ./... -v
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

---

## QUICK START

```bash
# 1. Start LiteLLM Proxy
pip install "litellm[proxy]"
cp proxy/.env.example proxy/.env  # Fill in API keys
python proxy/start_proxy.py

# 2. Use SDK (Python example)
cd sdk/python && pip install -e ".[dev]"
python -c "from llm_sdk import client; print(client.chat('Hello'))"
```

---

## NOTES

- Go SDK uses zero external dependencies (stdlib only)
- Python SDK requires Pydantic v2
- TypeScript SDK uses Zod for schema validation
- All SDKs share the same `sdk/prompts/` directory for templates
- K8s deployment uses Kustomize with HPA auto-scaling (2-6 replicas)

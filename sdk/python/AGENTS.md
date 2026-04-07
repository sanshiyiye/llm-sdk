# Python SDK

**Package:** `llm-sdk` (v0.2.0)  
**Python:** >=3.11  
**Dependencies:** openai>=1.30.0, httpx>=0.27.0, pydantic>=2.0.0

---

## STRUCTURE

```
python/
├── __init__.py         # Public exports
├── client.py           # LLMClient class (core)
├── errors.py           # Error hierarchy (8 types)
├── session.py          # Multi-turn Session
├── structured.py       # Pydantic-based structured output
├── templates.py        # Prompt template registry
├── pyproject.toml      # Package config
└── tests/
    └── test_sdk.py     # pytest suite
```

---

## QUICK START

```bash
pip install -e ".[dev]"
```

```python
from llm_sdk import client, templates
from pydantic import BaseModel

# Basic chat
reply = client.chat("Hello")

# Streaming
for chunk in client.chat_stream("Write a story"):
    print(chunk, end="")

# Structured output
class Product(BaseModel):
    name: str
    price: float

result = client.chat_structured("iPhone 16 Pro costs $999", schema=Product)

# Multi-turn session
session = client.session(system="You are a code reviewer")
r1 = session.chat("Review: def foo(): pass")
r2 = session.chat("What's wrong with it?")

# Templates
templates.load_dir("../prompts")
reply = templates.chat_with_template(client, "code_review",
    language="Python", focus="performance", code="x = []")
```

---

## CORE EXPORTS

**From `__init__.py`:**
- `LLMClient` — Main client class
- `client` — Singleton instance
- `Session` — Multi-turn conversation
- `chat_structured()` — Structured output helper
- `TemplateRegistry`, `templates` — Template system
- All error types (`LLMError`, `RateLimitError`, etc.)

---

## TESTING

```bash
pytest tests/ -v
```

Tests use `unittest.mock` to mock OpenAI client. See `tests/test_sdk.py`.

---

## NOTES

- Pydantic v2 required (checked at runtime)
- Uses `openai` client under the hood
- Auto-retry on RateLimit/Network errors (exponential backoff)
- No retry on Auth/Model errors

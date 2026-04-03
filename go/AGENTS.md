# Go SDK

**Module:** `github.com/yourorg/llm-sdk/go`  
**Go:** 1.22+  
**Dependencies:** None (stdlib only)

---

## STRUCTURE

```
go/
├── client.go       # LLMClient + core methods
├── errors.go       # Error hierarchy (8 types)
├── session.go      # Multi-turn Session
├── structured.go   # Struct-based JSON output
├── templates.go    # Prompt template registry
├── go.mod          # Module definition
└── client_test.go  # Test suite (external package)
```

---

## QUICK START

```bash
go test ./... -v
```

```go
package main

import (
    "context"
    "fmt"
    llmclient "github.com/yourorg/llm-sdk/go"
)

func main() {
    ctx := context.Background()
    c := llmclient.New()  // Reads LLM_BASE_URL, LLM_API_KEY from env

    // Basic chat
    reply, _ := c.Chat(ctx, "Hello", nil)
    fmt.Println(reply)

    // Streaming
    chunks, errc := c.ChatStream(ctx, "Write a story", nil)
    for chunk := range chunks { fmt.Print(chunk) }
    if err := <-errc; err != nil { panic(err) }

    // Structured output
    type Product struct {
        Name  string  `json:"name"`
        Price float64 `json:"price"`
    }
    var p Product
    _ = c.ChatStructured(ctx, "iPhone costs $999", &p, nil)

    // Multi-turn session
    sess := c.NewSession("You are a code reviewer")
    r1, _ := sess.Chat(ctx, "Review: var x int", nil)
    r2, _ := sess.Chat(ctx, "What's wrong?", nil)

    // Templates
    reg := llmclient.NewTemplateRegistry()
    reg.LoadDir("../prompts")
    result, _ := reg.ChatWithTemplate(ctx, c, "code_review",
        map[string]string{"language": "Go", "focus": "concurrency", "code": "var x int"}, nil)
}
```

---

## CORE API

**Client:**
- `New() *Client` — Create client (reads env)
- `Chat(ctx, prompt, opts) (string, error)`
- `ChatStream(ctx, prompt, opts) (<-chan string, <-chan error)`
- `Embed(ctx, text, opts) ([]float64, error)`
- `ChatStructured(ctx, prompt, dst, opts) error` — dst must be pointer to struct
- `NewSession(system) *Session`
- `ResolveModel(capability) (string, error)`

**Session:**
- `Chat(ctx, prompt, opts) (string, error)` — with history
- `ChatStream(ctx, prompt, opts) (<-chan string, <-chan error)`
- `ChatStructured(ctx, prompt, dst, opts) error`
- `Turns() int`, `History() []Message`
- `Clear()`

**Templates:**
- `NewTemplateRegistry() *TemplateRegistry`
- `Register(name, opts)`, `LoadDir(dir)`, `Get(name)`, `List()`
- `ChatWithTemplate(ctx, client, name, vars, opts)`

---

## TESTING

```bash
go test ./... -v
```

Tests use `httptest.Server` for HTTP mocking. See `client_test.go`.

---

## NOTES

- Zero external dependencies (stdlib only)
- Auto-retry with exponential backoff
- JSON schema generated from struct tags
- Token-aware history trimming (~6000 tokens)

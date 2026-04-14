package llmclient_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"github.com/goat/llm-sdk/sdk/go"
)

// ── Test server helper ────────────────────────────────────────────────────────

func newTestServer(t *testing.T, handler http.HandlerFunc) (*httptest.Server, *llmclient.Client) {
	t.Helper()
	srv := httptest.NewServer(handler)
	t.Cleanup(srv.Close)
	c := llmclient.New()
	c.BaseURL = srv.URL
	c.APIKey = "test-key"

	return srv, c
}

func chatHandler(reply string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		resp := map[string]any{
			"choices": []map[string]any{
				{"message": map[string]any{"content": reply, "role": "assistant"}},
			},
		}
		json.NewEncoder(w).Encode(resp)
	}
}

func embedHandler(vec []float64) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		resp := map[string]any{
			"data": []map[string]any{
				{"embedding": vec},
			},
		}
		json.NewEncoder(w).Encode(resp)
	}
}

// ── TAG routing ───────────────────────────────────────────────────────────────

func TestTagModelMap_AllCapabilities(t *testing.T) {
	c := llmclient.New()
	caps := []string{"chat", "vision", "video-input", "embedding", "image-gen", "fast", "local"}
	for _, cap := range caps {
		if _, err := c.ResolveModel(cap); err != nil {
			t.Errorf("ResolveModel(%q) returned error: %v", cap, err)
		}
	}
}

func TestTagModelMap_UnknownCapability(t *testing.T) {
	c := llmclient.New()
	if _, err := c.ResolveModel("nonexistent"); err == nil {
		t.Error("expected error for unknown capability, got nil")
	}
}

func TestTagModelMap_EnvOverride(t *testing.T) {
	t.Setenv("LLM_MODEL_CHAT", "my-custom-model")
	c := llmclient.New()
	m, err := c.ResolveModel("chat")
	if err != nil {
		t.Fatal(err)
	}
	if m != "my-custom-model" {
		t.Errorf("expected my-custom-model, got %s", m)
	}
}

// ── Chat ──────────────────────────────────────────────────────────────────────

func TestChat_BasicReply(t *testing.T) {
	_, c := newTestServer(t, chatHandler("你好！"))
	reply, err := c.Chat(context.Background(), "你好", nil)
	if err != nil {
		t.Fatal(err)
	}
	if reply != "你好！" {
		t.Errorf("expected '你好！', got %q", reply)
	}
}

func TestChat_WithSystem(t *testing.T) {
	var captured map[string]any
	_, c := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		json.NewDecoder(r.Body).Decode(&captured)
		chatHandler("ok")(w, r)
	})
	_, _ = c.Chat(context.Background(), "hi", &llmclient.ChatOpts{System: "you are helpful"})
	msgs := captured["messages"].([]any)
	first := msgs[0].(map[string]any)
	if first["role"] != "system" {
		t.Errorf("expected first message role=system, got %v", first["role"])
	}
}

func TestChat_ImageURLTriggerVision(t *testing.T) {
	var captured map[string]any
	_, c := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		json.NewDecoder(r.Body).Decode(&captured)
		chatHandler("ok")(w, r)
	})
	visionModel, _ := c.ResolveModel("vision")
	_, _ = c.Chat(context.Background(), "describe", &llmclient.ChatOpts{ImageURL: "https://example.com/img.png"})
	if captured["model"] != visionModel {
		t.Errorf("expected model=%s, got %v", visionModel, captured["model"])
	}
}

func TestChat_ExplicitModelBypassesTag(t *testing.T) {
	var captured map[string]any
	_, c := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		json.NewDecoder(r.Body).Decode(&captured)
		chatHandler("ok")(w, r)
	})
	_, _ = c.Chat(context.Background(), "hi", &llmclient.ChatOpts{Model: "gpt-chat"})
	if captured["model"] != "gpt-chat" {
		t.Errorf("expected gpt-chat, got %v", captured["model"])
	}
}

func TestChat_CacheHitAvoidsSecondRequest(t *testing.T) {
	calls := 0
	_, c := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		calls++
		chatHandler("cached")(w, r)
	})

	reply1, err := c.Chat(context.Background(), "hi", nil)
	if err != nil {
		t.Fatal(err)
	}
	reply2, err := c.Chat(context.Background(), "hi", nil)
	if err != nil {
		t.Fatal(err)
	}
	if reply1 != "cached" || reply2 != "cached" {
		t.Fatalf("unexpected replies: %q / %q", reply1, reply2)
	}
	if calls != 1 {
		t.Fatalf("expected 1 upstream call with cache hit, got %d", calls)
	}
}

func TestChat_CacheCanBeDisabledPerRequest(t *testing.T) {
	calls := 0
	_, c := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		calls++
		chatHandler("fresh")(w, r)
	})

	disabled := false
	_, err := c.Chat(context.Background(), "hi", &llmclient.ChatOpts{Cache: &disabled})
	if err != nil {
		t.Fatal(err)
	}
	_, err = c.Chat(context.Background(), "hi", &llmclient.ChatOpts{Cache: &disabled})
	if err != nil {
		t.Fatal(err)
	}
	if calls != 2 {
		t.Fatalf("expected 2 upstream calls when cache disabled, got %d", calls)
	}
}

// ── Embed ─────────────────────────────────────────────────────────────────────

func TestEmbed_ReturnsVector(t *testing.T) {
	expected := []float64{0.1, 0.2, 0.3}
	_, c := newTestServer(t, embedHandler(expected))
	vec, err := c.Embed(context.Background(), "test", nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(vec) != len(expected) {
		t.Fatalf("expected len %d, got %d", len(expected), len(vec))
	}
	for i, v := range vec {
		if v != expected[i] {
			t.Errorf("vec[%d]: expected %f, got %f", i, expected[i], v)
		}
	}
}

// ── ChatStructured ────────────────────────────────────────────────────────────

func TestChatStructured_ParsesJSON(t *testing.T) {
	type Product struct {
		Name  string  `json:"name"`
		Price float64 `json:"price"`
	}
	_, c := newTestServer(t, chatHandler(`{"name":"iPhone","price":7999}`))
	var p Product
	if err := c.ChatStructured(context.Background(), "extract", &p, nil); err != nil {
		t.Fatal(err)
	}
	if p.Name != "iPhone" {
		t.Errorf("expected iPhone, got %s", p.Name)
	}
	if p.Price != 7999 {
		t.Errorf("expected 7999, got %f", p.Price)
	}
}

func TestChatStructured_StripsMarkdownFence(t *testing.T) {
	type Item struct {
		Value int `json:"value"`
	}
	_, c := newTestServer(t, chatHandler("```json\n{\"value\":42}\n```"))
	var item Item
	if err := c.ChatStructured(context.Background(), "get", &item, nil); err != nil {
		t.Fatal(err)
	}
	if item.Value != 42 {
		t.Errorf("expected 42, got %d", item.Value)
	}
}

func TestChatStructured_ErrorOnInvalidJSON(t *testing.T) {
	type Item struct{ Value int `json:"value"` }
	_, c := newTestServer(t, chatHandler("not json at all"))
	var item Item
	err := c.ChatStructured(context.Background(), "get", &item, nil)
	if err == nil {
		t.Error("expected error, got nil")
	}
	if _, ok := err.(*llmclient.StructuredOutputError); !ok {
		t.Errorf("expected *StructuredOutputError, got %T", err)
	}
}

// ── Session ───────────────────────────────────────────────────────────────────

func TestSession_MaintainsHistory(t *testing.T) {
	callCount := 0
	var lastMessages []map[string]any
	_, c := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		callCount++
		var body map[string]any
		json.NewDecoder(r.Body).Decode(&body)
		msgs := body["messages"].([]any)
		lastMessages = make([]map[string]any, len(msgs))
		for i, m := range msgs {
			lastMessages[i] = m.(map[string]any)
		}
		chatHandler("reply" + string(rune('0'+callCount)))(w, r)
	})

	sess := c.NewSession("you are helpful")
	_, _ = sess.Chat(context.Background(), "q1", nil)
	_, _ = sess.Chat(context.Background(), "q2", nil)

	if sess.Turns() != 2 {
		t.Errorf("expected 2 turns, got %d", sess.Turns())
	}
	// Last call should include system + q1 + reply1 + q2
	userCount := 0
	for _, m := range lastMessages {
		if m["role"] == "user" {
			userCount++
		}
	}
	if userCount != 2 {
		t.Errorf("expected 2 user messages in last call, got %d", userCount)
	}
}

func TestSession_ClearResetsHistory(t *testing.T) {
	_, c := newTestServer(t, chatHandler("ok"))
	sess := c.NewSession("")
	_, _ = sess.Chat(context.Background(), "hi", nil)
	if sess.Turns() != 1 {
		t.Fatal("expected 1 turn")
	}
	sess.Clear()
	if sess.Turns() != 0 {
		t.Errorf("expected 0 turns after clear, got %d", sess.Turns())
	}
}

// ── TemplateRegistry ──────────────────────────────────────────────────────────

func TestTemplateRegistry_RegisterAndRender(t *testing.T) {
	reg := llmclient.NewTemplateRegistry()
	reg.Register("greet", "用 {lang} 打招呼", "")
	tmpl, err := reg.Get("greet")
	if err != nil {
		t.Fatal(err)
	}
	user, _, err := tmpl.Render(map[string]string{"lang": "日语"})
	if err != nil {
		t.Fatal(err)
	}
	if user != "用 日语 打招呼" {
		t.Errorf("unexpected render: %q", user)
	}
}

func TestTemplateRegistry_NotFoundError(t *testing.T) {
	reg := llmclient.NewTemplateRegistry()
	_, err := reg.Get("missing")
	if err == nil {
		t.Error("expected error, got nil")
	}
	if _, ok := err.(*llmclient.TemplateNotFoundError); !ok {
		t.Errorf("expected *TemplateNotFoundError, got %T", err)
	}
}

func TestTemplateRegistry_LoadDir(t *testing.T) {
	dir := t.TempDir()
	os.WriteFile(dir+"/hello.txt", []byte("system: 你是助手\n---\n你好 {name}"), 0644)
	os.WriteFile(dir+"/plain.txt", []byte("纯文本 {x}"), 0644)

	reg := llmclient.NewTemplateRegistry()
	n, err := reg.LoadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if n != 2 {
		t.Errorf("expected 2, got %d", n)
	}

	tmpl, _ := reg.Get("hello")
	user, sys, err := tmpl.Render(map[string]string{"name": "Claude"})
	if err != nil {
		t.Fatal(err)
	}
	if !containsStr(user, "Claude") {
		t.Errorf("user prompt missing name: %q", user)
	}
	if sys != "你是助手" {
		t.Errorf("unexpected system: %q", sys)
	}
}

// ── Errors ────────────────────────────────────────────────────────────────────

func TestErrors_ProxyErrorReturnsError(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.WriteHeader(500)
		w.Write([]byte(`{"error":{"message":"internal"}}`))
	}))
	defer srv.Close()
	c := llmclient.New()
	c.BaseURL = srv.URL
	_, err := c.Chat(context.Background(), "hi", nil)
	if err == nil {
		t.Fatal("expected error on proxy 500, got nil")
	}
	if calls != 1 {
		t.Errorf("expected exactly 1 call (no SDK retry), got %d", calls)
	}
}

func TestErrors_NoRetryOnAuthError(t *testing.T) {
	calls := 0
	_, c := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.WriteHeader(401)
		w.Write([]byte(`{"error":{"message":"unauthorized"}}`))
	})
	_, err := c.Chat(context.Background(), "hi", nil)
	if err == nil {
		t.Error("expected error, got nil")
	}
	if calls != 1 {
		t.Errorf("expected 1 call, got %d", calls)
	}
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func containsStr(s, sub string) bool {
	return len(s) > 0 && len(sub) > 0 &&
		(s == sub || len(s) >= len(sub) && func() bool {
			for i := 0; i <= len(s)-len(sub); i++ {
				if s[i:i+len(sub)] == sub {
					return true
				}
			}
			return false
		}())
}

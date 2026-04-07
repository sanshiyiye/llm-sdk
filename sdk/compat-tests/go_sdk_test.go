package llmclient_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	llmclient "github.com/goat/llm-sdk/sdk/go"
)

type weatherParams struct {
	City string `json:"city"`
}

type weatherTool struct{}

func (weatherTool) Name() string { return "get_weather" }

func (weatherTool) Description() string { return "获取天气" }

func (weatherTool) Parameters() interface{} { return weatherParams{} }

func (weatherTool) Execute(ctx context.Context, params interface{}) (string, error) {
	return params.(weatherParams).City + " 晴", nil
}

func newCompatClient(server *httptest.Server) *llmclient.Client {
	c := llmclient.New()
	c.BaseURL = server.URL
	c.APIKey = "test-key"
	c.MaxRetries = 1
	return c
}

func TestGoChatContracts(t *testing.T) {
	var bodies []map[string]interface{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]interface{}
		_ = json.NewDecoder(r.Body).Decode(&body)
		bodies = append(bodies, body)
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"choices": []map[string]interface{}{
				{"message": map[string]interface{}{"content": "Hello!"}},
			},
		})
	}))
	defer server.Close()

	c := newCompatClient(server)
	reply, err := c.Chat(context.Background(), "Hello", nil)
	if err != nil {
		t.Fatalf("chat failed: %v", err)
	}
	if reply != "Hello!" {
		t.Fatalf("expected Hello!, got %q", reply)
	}
	if bodies[0]["model"] != "auto-chat" {
		t.Fatalf("expected default chat model, got %v", bodies[0]["model"])
	}

	_, err = c.Chat(context.Background(), "Hello", &llmclient.ChatOpts{Model: "gpt-chat"})
	if err != nil {
		t.Fatalf("chat with model override failed: %v", err)
	}
	if bodies[1]["model"] != "gpt-chat" {
		t.Fatalf("expected explicit model override, got %v", bodies[1]["model"])
	}
}

func TestGoStructuredAndSessionContracts(t *testing.T) {
	callCount := 0
	var lastBody map[string]interface{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		_ = json.NewDecoder(r.Body).Decode(&lastBody)
		w.Header().Set("Content-Type", "application/json")
		if callCount == 1 {
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"choices": []map[string]interface{}{
					{"message": map[string]interface{}{"content": "```json\n{\"value\":42}\n```"}},
				},
			})
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"choices": []map[string]interface{}{
				{"message": map[string]interface{}{"content": "reply"}},
			},
		})
	}))
	defer server.Close()

	c := newCompatClient(server)
	var item struct {
		Value int `json:"value"`
	}
	if err := c.ChatStructured(context.Background(), "extract", &item, nil); err != nil {
		t.Fatalf("structured output failed: %v", err)
	}
	if item.Value != 42 {
		t.Fatalf("expected 42, got %d", item.Value)
	}

	sess := c.NewSession("你是助手")
	if _, err := sess.Chat(context.Background(), "你好", nil); err != nil {
		t.Fatalf("session first turn failed: %v", err)
	}
	if _, err := sess.Chat(context.Background(), "继续", nil); err != nil {
		t.Fatalf("session second turn failed: %v", err)
	}
	messages := lastBody["messages"].([]interface{})
	if len(messages) < 4 {
		t.Fatalf("expected history in second session call, got %#v", messages)
	}
}

func TestGoCacheContract(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"choices": []map[string]interface{}{
				{"message": map[string]interface{}{"content": "cached"}},
			},
		})
	}))
	defer server.Close()

	c := newCompatClient(server)
	reply1, err := c.Chat(context.Background(), "cache me", nil)
	if err != nil {
		t.Fatalf("first chat failed: %v", err)
	}
	reply2, err := c.Chat(context.Background(), "cache me", nil)
	if err != nil {
		t.Fatalf("second chat failed: %v", err)
	}
	if reply1 != "cached" || reply2 != "cached" {
		t.Fatalf("unexpected cache replies: %q / %q", reply1, reply2)
	}
	if calls != 1 {
		t.Fatalf("expected one upstream call with cache hit, got %d", calls)
	}
}

func TestGoToolUseContract(t *testing.T) {
	callCount := 0
	var lastBody map[string]interface{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		_ = json.NewDecoder(r.Body).Decode(&lastBody)
		w.Header().Set("Content-Type", "application/json")
		if callCount == 1 {
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"choices": []map[string]interface{}{
					{
						"message": map[string]interface{}{
							"content": "",
							"tool_calls": []map[string]interface{}{
								{
									"id":   "call_1",
									"type": "function",
									"function": map[string]interface{}{
										"name":      "get_weather",
										"arguments": "{\"city\":\"北京\"}",
									},
								},
							},
						},
					},
				},
			})
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"choices": []map[string]interface{}{
				{"message": map[string]interface{}{"content": "北京今天是晴天"}},
			},
		})
	}))
	defer server.Close()

	c := newCompatClient(server)
	if err := c.ChatWithTools(context.Background(), "北京天气如何？", weatherTool{}, nil); err != nil {
		t.Fatalf("tool use failed: %v", err)
	}
	messages := lastBody["messages"].([]interface{})
	foundToolResult := false
	for _, message := range messages {
		msg := message.(map[string]interface{})
		if msg["role"] == "tool" && msg["tool_call_id"] == "call_1" && msg["content"] == "北京 晴" {
			foundToolResult = true
		}
	}
	if !foundToolResult {
		t.Fatalf("expected tool result message, got %#v", messages)
	}
}

func TestGoAuthErrorDoesNotRetry(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"error":{"message":"unauthorized"}}`))
	}))
	defer server.Close()

	c := newCompatClient(server)
	_, err := c.Chat(context.Background(), "auth", nil)
	if err == nil {
		t.Fatal("expected auth error")
	}
	if calls != 1 {
		t.Fatalf("expected no retry on auth error, got %d calls", calls)
	}
}

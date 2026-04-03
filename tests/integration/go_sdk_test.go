package llmclient_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	llmclient "github.com/yourorg/llm-sdk/go"
)

func setupMockServer(t *testing.T) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/v1/chat/completions":
			resp := map[string]interface{}{
				"choices": []map[string]interface{}{
					{"message": map[string]interface{}{"content": "Hello!"}},
				},
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(resp)
		case "/v1/embeddings":
			resp := map[string]interface{}{
				"data": []map[string]interface{}{
					{"embedding": []float64{0.1, 0.2, 0.3}},
				},
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(resp)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
}

func TestBasicChat(t *testing.T) {
	server := setupMockServer(t)
	defer server.Close()

	c := llmclient.New()
	ctx := context.Background()
	reply, err := c.Chat(ctx, "Hello", nil)

	if err != nil {
		t.Fatalf("chat failed: %v", err)
	}
	if reply == "" {
		t.Error("expected non-empty reply")
	}
}

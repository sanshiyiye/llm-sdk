package llmclient_test

import (
	"context"
	"encoding/json"
	"net/http"
	"testing"

	"github.com/goat/llm-sdk/sdk/go"
)

type weatherParams struct {
	City string `json:"city" description:"城市名称"`
}

type weatherTool struct{}

func (weatherTool) Name() string { return "get_weather" }

func (weatherTool) Description() string { return "获取天气" }

func (weatherTool) Parameters() interface{} { return weatherParams{} }

func (weatherTool) Execute(ctx context.Context, params interface{}) (string, error) {
	p := params.(weatherParams)
	return p.City + " 晴", nil
}

func TestChatWithTools_ExecutesToolLoop(t *testing.T) {
	callCount := 0
	var capturedBodies []map[string]interface{}
	_, client := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		callCount++
		var body map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		capturedBodies = append(capturedBodies, body)
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
										"arguments": `{"city":"北京"}`,
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
	})

	err := client.ChatWithTools(context.Background(), "北京天气如何？", weatherTool{}, nil)
	if err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if len(capturedBodies) != 2 {
		t.Fatalf("expected 2 calls, got %d", len(capturedBodies))
	}
	firstTools := capturedBodies[0]["tools"].([]interface{})
	firstTool := firstTools[0].(map[string]interface{})
	function := firstTool["function"].(map[string]interface{})
	if function["name"] != "get_weather" {
		t.Fatalf("expected tool name get_weather, got %v", function["name"])
	}
	secondMessages := capturedBodies[1]["messages"].([]interface{})
	foundToolResult := false
	for _, msg := range secondMessages {
		message := msg.(map[string]interface{})
		if message["role"] == "tool" && message["content"] == "北京 晴" && message["tool_call_id"] == "call_1" {
			foundToolResult = true
		}
	}
	if !foundToolResult {
		t.Fatalf("expected second request to include tool result message, got %#v", secondMessages)
	}
}

func TestToolDefinition_BuildsJSONSchema(t *testing.T) {
	definition := llmclient.ToolDefinition(weatherTool{})
	function := definition["function"].(map[string]interface{})
	parameters := function["parameters"].(map[string]interface{})
	properties := parameters["properties"].(map[string]interface{})
	city := properties["city"].(map[string]interface{})
	if city["type"] != "string" {
		t.Fatalf("expected city type string, got %v", city["type"])
	}
	required := parameters["required"].([]string)
	if len(required) != 1 || required[0] != "city" {
		t.Fatalf("unexpected required fields: %#v", required)
	}
}

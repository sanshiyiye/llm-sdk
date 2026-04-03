// Package llmclient provides Tool Use / Function Calling support.
//
// Usage:
//
//	type WeatherParams struct {
//		City string `json:"city" description:"城市名称"`
//	}
//
//	type WeatherTool struct{}
//
//	func (w WeatherTool) Name() string { return "get_weather" }
//	func (w WeatherTool) Description() string { return "获取城市天气" }
//	func (w WeatherTool) Parameters() interface{} { return WeatherParams{} }
//	func (w WeatherTool) Execute(ctx context.Context, params interface{}) (string, error) {
//		p := params.(WeatherParams)
//		return weatherAPI.Fetch(p.City), nil
//	}
//
//	// Use with client
//	err := c.ChatWithTools(ctx, "北京天气如何?", &WeatherTool{}, nil)
package llmclient

import (
	"context"
	"encoding/json"
	"fmt"
	"reflect"
)

// Tool is the interface that all tools must implement.
type Tool interface {
	Name() string
	Description() string
	Parameters() interface{}
	Execute(ctx context.Context, params interface{}) (string, error)
}

// toolCall represents a single tool call from the LLM.
type toolCall struct {
	Index    int
	ID      string
	Name    string
	Args    map[string]interface{}
}

// ToolDefinition converts a Tool to OpenAI function calling format.
func ToolDefinition(t Tool) map[string]interface{} {
	return map[string]interface{}{
		"type": "function",
		"function": map[string]interface{}{
			"name":        t.Name(),
			"description": t.Description(),
			"parameters":  jsonSchema(t.Parameters()),
		},
	}
}

// jsonSchema converts a Go struct to JSON Schema.
func jsonSchema(v interface{}) map[string]interface{} {
	if v == nil {
		return map[string]interface{}{"type": "object"}
	}

	t := reflect.TypeOf(v)
	if t.Kind() == reflect.Ptr {
		t = t.Elem()
	}
	if t.Kind() != reflect.Struct {
		return map[string]interface{}{"type": "object"}
	}

	properties := make(map[string]interface{})
	required := []string{}

	for i := 0; i < t.NumField(); i++ {
		field := t.Field(i)
		jsonTag := field.Tag.Get("json")
		descTag := field.Tag.Get("description")

		// Parse json tag (e.g., "city,omitempty")
		name := field.Name
		if jsonTag != "" {
			if n, _, _ := parseTag(jsonTag); n != "" {
				name = n
			}
		}

		// Field type to JSON Schema type
		fieldType := goTypeToJSON(field.Type)

		prop := map[string]interface{}{
			"type": fieldType,
		}
		if descTag != "" {
			prop["description"] = descTag
		}

		properties[name] = prop

		// Check if required (no omitempty)
		if jsonTag == "" || !containsOmitEmpty(jsonTag) {
			required = append(required, name)
		}
	}

	result := map[string]interface{}{
		"type":       "object",
		"properties": properties,
	}
	if len(required) > 0 {
		result["required"] = required
	}

	return result
}

func parseTag(tag string) (name string, omitEmpty bool, anyOther bool) {
	parts := splitTag(tag)
	if len(parts) == 0 {
		return "", false, false
	}
	name = parts[0]
	for _, p := range parts[1:] {
		switch p {
		case "omitempty":
			omitEmpty = true
		default:
			anyOther = true
		}
	}
	return name, omitEmpty, anyOther
}

func containsOmitEmpty(tag string) bool {
	return len(tag) > 0 && (tag == "omitempty" || len(tag) > 10 && tag[:10] == "omitempty")
}

func splitTag(s string) []string {
	var result []string
	var current []rune
	for _, r := range s {
		if r == ',' {
			result = append(result, string(current))
			current = nil
		} else {
			current = append(current, r)
		}
	}
	if len(current) > 0 {
		result = append(result, string(current))
	}
	return result
}

func goTypeToJSON(t reflect.Type) string {
	if t == nil {
		return "string"
	}

	// Handle pointers
	if t.Kind() == reflect.Ptr {
		return goTypeToJSON(t.Elem())
	}

	switch t.Kind() {
	case reflect.Bool:
		return "boolean"
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		return "integer"
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		return "integer"
	case reflect.Float32, reflect.Float64:
		return "number"
	case reflect.String:
		return "string"
	case reflect.Slice, reflect.Array:
		return "array"
	case reflect.Map:
		return "object"
	case reflect.Struct:
		return "object"
	default:
		return "string"
	}
}

// ChatWithTools executes a chat with tool calling capability.
// It automatically handles the tool call loop: LLM requests tool -> execute -> return result -> continue.
func (c *Client) ChatWithTools(ctx context.Context, prompt string, tool Tool, opts *ChatOpts) error {
	// Build tool definition
	toolDef := ToolDefinition(tool)

	// Build messages
	messages := c.buildMessages(prompt, opts)
	if opts == nil {
		opts = &ChatOpts{}
	}

	// Tool call loop
	maxCalls := 10
	for i := 0; i < maxCalls; i++ {
		// Call with tools
		body := map[string]interface{}{
			"model":    "auto-chat", // Use default, or from opts
			"messages": messages,
			"tools":    []map[string]interface{}{toolDef},
		}

		// Add other options
		if opts.Temperature != nil {
			body["temperature"] = *opts.Temperature
		}
		if opts.MaxTokens > 0 {
			body["max_tokens"] = opts.MaxTokens
		}

		// Make request
		var respData struct {
			Choices []struct {
				Message struct {
					Content     string `json:"content"`
					ToolCalls   []struct {
						ID       string          `json:"id"`
						Type     string          `json:"type"`
						Function struct {
							Name      string          `json:"name"`
							Arguments json.RawMessage `json:"arguments"`
						} `json:"function"`
					} `json:"tool_calls"`
				} `json:"message"`
			} `json:"choices"`
		}

		err := c.withRetry(ctx, func() error {
			resp, err := c.postJSON(ctx, "/v1/chat/completions", body)
			if err != nil {
				return err
			}
			defer resp.Body.Close()

			raw, _ := readAll(resp.Body)
			if resp.StatusCode >= 400 {
				return classifyError(resp.StatusCode, string(raw))
			}
			return json.Unmarshal(raw, &respData)
		})
		if err != nil {
			return err
		}

		if len(respData.Choices) == 0 {
			return fmt.Errorf("no response from LLM")
		}

		msg := respData.Choices[0].Message

		// Add assistant message
		messages = append(messages, Message{
			Role:    "assistant",
			Content: msg.Content,
		})

		// Check for tool calls
		if len(msg.ToolCalls) == 0 {
			// No tool calls, return the content
			fmt.Printf("%s\n", msg.Content)
			return nil
		}

		// Execute tool calls
		for _, tc := range msg.ToolCalls {
			if tc.Type != "function" {
				continue
			}

			var args map[string]interface{}
			if err := json.Unmarshal(tc.Function.Arguments, &args); err != nil {
				args = make(map[string]interface{})
			}

			// Execute tool
			result, err := tool.Execute(ctx, args)
			if err != nil {
				result = fmt.Sprintf("Error: %v", err)
			}

			// Add tool result message
			messages = append(messages, Message{
				Role:    "tool",
				Content: result,
			})
		}
	}

	return fmt.Errorf("tool call limit reached")
}

// readAll is a simple helper to read entire response
func readAll(respBody interface{ Read([]byte) (int, error) }) ([]byte, error) {
	buf := make([]byte, 4096)
	var result []byte
	for {
		n, err := respBody.Read(buf)
		result = append(result, buf[:n]...)
		if err != nil {
			break
		}
	}
	return result, nil
}

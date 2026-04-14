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
	"io"
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
	if opts == nil {
		opts = &ChatOpts{}
	}
	toolDef := ToolDefinition(tool)
	model, err := c.resolveOpts(opts, opts.ImageURL != "")
	if err != nil {
		return err
	}
	baseMessages := c.buildMessages(prompt, opts)
	messages := make([]map[string]interface{}, 0, len(baseMessages))
	for _, msg := range baseMessages {
		messages = append(messages, map[string]interface{}{
			"role":    msg.Role,
			"content": msg.Content,
		})
	}

	maxCalls := 10
	for i := 0; i < maxCalls; i++ {
		body := map[string]interface{}{
			"model":    model,
			"messages": messages,
			"tools":    []map[string]interface{}{toolDef},
			"tool_choice": "auto",
		}

		// Add other options
		if opts.Temperature != nil {
			body["temperature"] = *opts.Temperature
		}
		if opts.MaxTokens > 0 {
			body["max_tokens"] = opts.MaxTokens
		}

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

		resp, err := c.postJSON(ctx, "/v1/chat/completions", body)
		if err != nil {
			return err
		}
		raw, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode >= 400 {
			return classifyError(resp.StatusCode, string(raw))
		}
		if err := json.Unmarshal(raw, &respData); err != nil {
			return err
		}

		if len(respData.Choices) == 0 {
			return fmt.Errorf("no response from LLM")
		}

		msg := respData.Choices[0].Message
		assistantMessage := map[string]interface{}{
			"role":    "assistant",
			"content": msg.Content,
		}
		if len(msg.ToolCalls) > 0 {
			toolCalls := make([]map[string]interface{}, 0, len(msg.ToolCalls))
			for _, tc := range msg.ToolCalls {
				arguments := string(tc.Function.Arguments)
				var encoded string
				if err := json.Unmarshal(tc.Function.Arguments, &encoded); err == nil {
					arguments = encoded
				}
				toolCalls = append(toolCalls, map[string]interface{}{
					"id":   tc.ID,
					"type": tc.Type,
					"function": map[string]interface{}{
						"name":      tc.Function.Name,
						"arguments": arguments,
					},
				})
			}
			assistantMessage["tool_calls"] = toolCalls
		}
		messages = append(messages, assistantMessage)

		if len(msg.ToolCalls) == 0 {
			return nil
		}

		for _, tc := range msg.ToolCalls {
			if tc.Type != "function" {
				continue
			}

			var args map[string]interface{}
			if err := json.Unmarshal(tc.Function.Arguments, &args); err != nil {
				var encoded string
				if err := json.Unmarshal(tc.Function.Arguments, &encoded); err == nil {
					_ = json.Unmarshal([]byte(encoded), &args)
				}
				if args == nil {
					args = make(map[string]interface{})
				}
			}

			params, err := decodeToolArguments(tool.Parameters(), args)
			if err != nil {
				params = args
			}
			result, err := tool.Execute(ctx, params)
			if err != nil {
				result = fmt.Sprintf("Error: %v", err)
			}

			messages = append(messages, map[string]interface{}{
				"role":         "tool",
				"tool_call_id": tc.ID,
				"content":      result,
			})
		}
	}

	return fmt.Errorf("tool call limit reached")
}

func decodeToolArguments(template interface{}, args map[string]interface{}) (interface{}, error) {
	if template == nil {
		return args, nil
	}
	raw, err := json.Marshal(args)
	if err != nil {
		return nil, err
	}
	targetType := reflect.TypeOf(template)
	if targetType.Kind() == reflect.Ptr {
		value := reflect.New(targetType.Elem())
		if err := json.Unmarshal(raw, value.Interface()); err != nil {
			return nil, err
		}
		return value.Interface(), nil
	}
	value := reflect.New(targetType)
	if err := json.Unmarshal(raw, value.Interface()); err != nil {
		return nil, err
	}
	return value.Elem().Interface(), nil
}

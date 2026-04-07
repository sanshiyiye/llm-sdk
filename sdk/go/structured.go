package llmclient

import (
	"context"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
)

// ChatStructured sends a chat request and unmarshals the response into dst.
// dst must be a pointer to a struct.
//
// Usage:
//
//	type Product struct {
//	    Name  string  `json:"name"`
//	    Price float64 `json:"price"`
//	}
//	var p Product
//	err := c.ChatStructured(ctx, "提取商品信息：iPhone 售价 7999", &p, nil)
func (c *Client) ChatStructured(ctx context.Context, prompt string, dst any, opts *ChatOpts) error {
	schema, err := buildJSONSchema(dst)
	if err != nil {
		return fmt.Errorf("llmclient: failed to build JSON schema: %w", err)
	}

	systemPrompt := buildStructuredSystemPrompt(schema)
	if opts == nil {
		opts = &ChatOpts{}
	}
	merged := &ChatOpts{
		System:      combineSystem(opts.System, systemPrompt),
		History:     opts.History,
		Capability:  opts.Capability,
		Model:       opts.Model,
		MaxTokens:   opts.MaxTokens,
		Temperature: opts.Temperature,
	}

	raw, err := c.Chat(ctx, prompt, merged)
	if err != nil {
		return err
	}

	jsonStr := extractJSON(raw)
	if err := json.Unmarshal([]byte(jsonStr), dst); err != nil {
		return &StructuredOutputError{
			LLMError:    LLMError{Message: fmt.Sprintf("structured output parse failed: %v", err)},
			RawResponse: raw,
		}
	}
	return nil
}

// ── Helpers ───────────────────────────────────────────────────────────────────

var mdFenceRe = regexp.MustCompile("(?s)```(?:json)?\\s*(.+?)\\s*```")

func extractJSON(text string) string {
	text = strings.TrimSpace(text)
	if m := mdFenceRe.FindStringSubmatch(text); len(m) == 2 {
		return strings.TrimSpace(m[1])
	}
	start := strings.Index(text, "{")
	end := strings.LastIndex(text, "}")
	if start != -1 && end > start {
		return text[start : end+1]
	}
	return text
}

func buildStructuredSystemPrompt(schema string) string {
	return "请严格按照以下 JSON Schema 返回结果。\n" +
		"只返回合法的 JSON 对象，不要包含 Markdown 代码块、注释或任何其他内容。\n\n" +
		"Schema:\n" + schema
}

func combineSystem(userSystem, structuredSystem string) string {
	if userSystem == "" {
		return structuredSystem
	}
	return userSystem + "\n\n" + structuredSystem
}

// buildJSONSchema generates a minimal JSON Schema from a Go struct via
// marshaling to a map and building field descriptions from json tags.
// For production use, consider replacing with a dedicated schema library.
func buildJSONSchema(v any) (string, error) {
	// Marshal to JSON to discover fields, then wrap in a schema envelope.
	// This gives us field names from json tags automatically.
	b, err := json.Marshal(v)
	if err != nil {
		return "", err
	}
	var fields map[string]any
	if err := json.Unmarshal(b, &fields); err != nil {
		return "", fmt.Errorf("dst must be a pointer to a struct, got: %T", v)
	}

	properties := make(map[string]any, len(fields))
	required := make([]string, 0, len(fields))
	for k, val := range fields {
		typ := jsonType(val)
		properties[k] = map[string]any{"type": typ}
		required = append(required, k)
	}

	schema := map[string]any{
		"type":       "object",
		"properties": properties,
		"required":   required,
	}
	out, err := json.MarshalIndent(schema, "", "  ")
	if err != nil {
		return "", err
	}
	return string(out), nil
}

func jsonType(v any) string {
	switch v.(type) {
	case float64:
		return "number"
	case bool:
		return "boolean"
	case []any:
		return "array"
	case map[string]any:
		return "object"
	case nil:
		return "null"
	default:
		return "string"
	}
}

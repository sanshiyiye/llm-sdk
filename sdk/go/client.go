// Package llmclient provides a unified LLM client that routes
// requests through a LiteLLM Proxy using capability tags.
//
// Retries are handled by the LiteLLM Proxy; the SDK does not retry.
//
// Usage:
//
//	c := llmclient.New()
//	reply, _ := c.Chat(ctx, "你好", nil)
//	reply, _ := c.Chat(ctx, "describe", &llmclient.ChatOpts{ImageURL: "https://..."})
//	vec,   _ := c.Embed(ctx, "some text", nil)
//	ch,    _ := c.ChatStream(ctx, "write an article", nil)
//	for chunk := range ch { fmt.Print(chunk) }
package llmclient

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

// ── Capability tag → model_name mapping ──────────────────────────────────────

var defaultTagMap = map[string]string{
	"chat":        "auto-chat",
	"vision":      "auto-vision",
	"video-input": "gemini-vision",
	"embedding":   "text-embedding",
	"image-gen":   "gpt-image-gen",
	"fast":        "gemini-chat",
	"local":       "local-chat",
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ── Client ────────────────────────────────────────────────────────────────────

// Client is the main LLM SDK client.
type Client struct {
	BaseURL string
	APIKey  string
	TagMap  map[string]string
	HTTP    *http.Client
	Cache   CacheBackend
}

// New creates a Client configured from environment variables.
func New() *Client {
	return &Client{
		BaseURL: envOr("LLM_BASE_URL", "http://localhost:4000"),
		APIKey:  envOr("LLM_API_KEY", "no-key"),
		TagMap: map[string]string{
			"chat":        envOr("LLM_MODEL_CHAT", defaultTagMap["chat"]),
			"vision":      envOr("LLM_MODEL_VISION", defaultTagMap["vision"]),
			"video-input": envOr("LLM_MODEL_VIDEO", defaultTagMap["video-input"]),
			"embedding":   envOr("LLM_MODEL_EMBEDDING", defaultTagMap["embedding"]),
			"image-gen":   envOr("LLM_MODEL_IMAGE_GEN", defaultTagMap["image-gen"]),
			"fast":        envOr("LLM_MODEL_FAST", defaultTagMap["fast"]),
			"local":       envOr("LLM_MODEL_LOCAL", defaultTagMap["local"]),
		},
		HTTP:  &http.Client{Timeout: 60 * time.Second},
		Cache:      NewTTLCache(1000, time.Hour),
	}
}

// ResolveModel maps a capability tag to a model_name.
func (c *Client) ResolveModel(capability string) (string, error) {
	if m, ok := c.TagMap[capability]; ok {
		return m, nil
	}
	return "", fmt.Errorf("unknown capability %q; valid: chat/vision/video-input/embedding/image-gen/fast/local", capability)
}

// ── Message types ─────────────────────────────────────────────────────────────

// Message represents a single chat message.
type Message struct {
	Role    string `json:"role"`
	Content any    `json:"content"` // string | []ContentPart
}

// ContentPart is one element of a multimodal message.
type ContentPart struct {
	Type     string    `json:"type"`
	Text     string    `json:"text,omitempty"`
	ImageURL *ImageURL `json:"image_url,omitempty"`
}

// ImageURL holds a URL for an image content part.
type ImageURL struct {
	URL string `json:"url"`
}

// ── Chat ──────────────────────────────────────────────────────────────────────

// ChatOpts configures a Chat or ChatStream request.
type ChatOpts struct {
	System      string
	History     []Message
	ImageURL    string
	Capability  string
	Model       string // direct model_name, bypasses tag routing
	MaxTokens   int
	Temperature *float64
	Cache       *bool
}

// Chat sends a single chat request and returns the reply.
func (c *Client) Chat(ctx context.Context, prompt string, opts *ChatOpts) (string, error) {
	if opts == nil {
		opts = &ChatOpts{}
	}
	model, err := c.resolveOpts(opts, opts.ImageURL != "")
	if err != nil {
		return "", err
	}
	messages := c.buildMessages(prompt, opts)
	body := c.buildBody(model, messages, opts)
	useCache := c.Cache != nil && (opts.Cache == nil || *opts.Cache)

	if useCache {
		cacheKey := BuildCacheKey(model, messages)
		if cacheKey != "" {
			if cached, ok := c.Cache.Get(cacheKey); ok {
				if reply, ok := cached.(string); ok {
					return reply, nil
				}
			}
		}
	}

	resp, err := c.postJSON(ctx, "/v1/chat/completions", body)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return "", classifyError(resp.StatusCode, string(raw))
	}
	var out struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
		Error *struct{ Message string `json:"message"` } `json:"error"`
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return "", &NetworkError{LLMError{Message: "failed to decode response: " + err.Error()}}
	}
	if out.Error != nil {
		return "", &ModelError{LLMError{Message: out.Error.Message}}
	}
	if len(out.Choices) == 0 {
		return "", &ProxyError{LLMError{Message: "empty response from proxy"}}
	}
	result := out.Choices[0].Message.Content
	if useCache {
		cacheKey := BuildCacheKey(model, messages)
		if cacheKey != "" {
			c.Cache.Set(cacheKey, result, 0)
		}
	}
	return result, nil
}

// ── ChatStream ────────────────────────────────────────────────────────────────

// ChatStream sends a streaming chat request.
// Returns a channel that yields text chunks; closed when done.
// The second return value is an error channel; read after the text channel closes.
func (c *Client) ChatStream(ctx context.Context, prompt string, opts *ChatOpts) (<-chan string, <-chan error) {
	chunks := make(chan string, 32)
	errc := make(chan error, 1)

	if opts == nil {
		opts = &ChatOpts{}
	}

	go func() {
		defer close(chunks)
		defer close(errc)

		model, err := c.resolveOpts(opts, opts.ImageURL != "")
		if err != nil {
			errc <- err
			return
		}
		messages := c.buildMessages(prompt, opts)
		body := c.buildBody(model, messages, opts)
		body["stream"] = true

		resp, err := c.postJSON(ctx, "/v1/chat/completions", body)
		if err != nil {
			errc <- &NetworkError{LLMError{Message: err.Error()}}
			return
		}
		defer resp.Body.Close()

		if resp.StatusCode >= 400 {
			raw, _ := io.ReadAll(resp.Body)
			errc <- classifyError(resp.StatusCode, string(raw))
			return
		}

		scanner := bufio.NewScanner(resp.Body)
		for scanner.Scan() {
			line := scanner.Text()
			if !strings.HasPrefix(line, "data: ") {
				continue
			}
			data := strings.TrimPrefix(line, "data: ")
			if data == "[DONE]" {
				break
			}
			var ev struct {
				Choices []struct {
					Delta struct {
						Content string `json:"content"`
					} `json:"delta"`
				} `json:"choices"`
			}
			if err := json.Unmarshal([]byte(data), &ev); err != nil {
				continue
			}
			if len(ev.Choices) > 0 && ev.Choices[0].Delta.Content != "" {
				select {
				case chunks <- ev.Choices[0].Delta.Content:
				case <-ctx.Done():
					return
				}
			}
		}
		if err := scanner.Err(); err != nil {
			errc <- &NetworkError{LLMError{Message: err.Error()}}
		}
	}()

	return chunks, errc
}

// ── Embed ─────────────────────────────────────────────────────────────────────

// EmbedOpts configures an Embed request.
type EmbedOpts struct {
	Model string
}

// Embed returns a single embedding vector for the given text.
func (c *Client) Embed(ctx context.Context, text string, opts *EmbedOpts) ([]float64, error) {
	model := ""
	if opts != nil && opts.Model != "" {
		model = opts.Model
	} else {
		var err error
		model, err = c.ResolveModel("embedding")
		if err != nil {
			return nil, err
		}
	}

	body := map[string]any{"model": model, "input": text}
	resp, err := c.postJSON(ctx, "/v1/embeddings", body)
	if err != nil {
		return nil, &NetworkError{LLMError{Message: err.Error()}}
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, classifyError(resp.StatusCode, string(raw))
	}
	var out struct {
		Data  []struct{ Embedding []float64 `json:"embedding"` } `json:"data"`
		Error *struct{ Message string `json:"message"` }        `json:"error"`
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, &NetworkError{LLMError{Message: err.Error()}}
	}
	if out.Error != nil {
		return nil, &ModelError{LLMError{Message: out.Error.Message}}
	}
	if len(out.Data) == 0 {
		return nil, &ProxyError{LLMError{Message: "empty embedding response"}}
	}
	return out.Data[0].Embedding, nil
}

// ── Session ───────────────────────────────────────────────────────────────────

// NewSession creates a new multi-turn Session.
func (c *Client) NewSession(system string) *Session {
	return &Session{client: c, system: system}
}

// ── Internal helpers ──────────────────────────────────────────────────────────

func (c *Client) resolveOpts(opts *ChatOpts, hasImage bool) (string, error) {
	if opts.Model != "" {
		return opts.Model, nil
	}
	cap := opts.Capability
	if cap == "" {
		if hasImage {
			cap = "vision"
		} else {
			cap = "chat"
		}
	}
	return c.ResolveModel(cap)
}

func (c *Client) buildMessages(prompt string, opts *ChatOpts) []Message {
	var msgs []Message
	if opts.System != "" {
		msgs = append(msgs, Message{Role: "system", Content: opts.System})
	}
	msgs = append(msgs, opts.History...)

	if opts.ImageURL != "" {
		parts := []ContentPart{
			{Type: "text", Text: prompt},
			{Type: "image_url", ImageURL: &ImageURL{URL: opts.ImageURL}},
		}
		msgs = append(msgs, Message{Role: "user", Content: parts})
	} else {
		msgs = append(msgs, Message{Role: "user", Content: prompt})
	}
	return msgs
}

func (c *Client) buildBody(model string, messages []Message, opts *ChatOpts) map[string]any {
	body := map[string]any{
		"model":    model,
		"messages": messages,
	}
	if opts.MaxTokens > 0 {
		body["max_tokens"] = opts.MaxTokens
	}
	if opts.Temperature != nil {
		body["temperature"] = *opts.Temperature
	}
	return body
}

func (c *Client) postJSON(ctx context.Context, path string, body map[string]any) (*http.Response, error) {
	b, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+path, bytes.NewReader(b))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	return c.HTTP.Do(req)
}


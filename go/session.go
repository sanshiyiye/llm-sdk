package llmclient

import (
	"context"
	"strings"
)

const maxHistoryTokens = 6000

// Session manages a multi-turn conversation with automatic history tracking.
//
// Usage:
//
//	sess := c.NewSession("你是代码审查助手")
//	r1, _ := sess.Chat(ctx, "审查这段代码：...", nil)
//	r2, _ := sess.Chat(ctx, "给出修复方案", nil)
//	sess.Clear()
type Session struct {
	client  *Client
	system  string
	history []Message
}

// Turns returns the number of completed conversation rounds.
func (s *Session) Turns() int { return len(s.history) / 2 }

// History returns a snapshot of the current history (excluding system).
func (s *Session) History() []Message {
	out := make([]Message, len(s.history))
	copy(out, s.history)
	return out
}

// Clear resets the conversation history while preserving the system prompt.
func (s *Session) Clear() { s.history = nil }

func estimateTokens(text string) int {
	n := len(text) / 4
	if n < 1 {
		return 1
	}
	return n
}

func (s *Session) trimHistory() {
	for len(s.history) >= 2 {
		total := 0
		for _, m := range s.history {
			switch v := m.Content.(type) {
			case string:
				total += estimateTokens(v)
			default:
				total += 50 // rough estimate for multimodal parts
			}
		}
		if total <= maxHistoryTokens {
			break
		}
		s.history = s.history[2:] // drop oldest user+assistant pair
	}
}

func (s *Session) append(role, content string) {
	s.history = append(s.history, Message{Role: role, Content: content})
	s.trimHistory()
}

// Chat sends one turn, automatically carrying conversation history.
func (s *Session) Chat(ctx context.Context, prompt string, opts *ChatOpts) (string, error) {
	if opts == nil {
		opts = &ChatOpts{}
	}
	merged := &ChatOpts{
		System:      s.system,
		History:     s.history,
		ImageURL:    opts.ImageURL,
		Capability:  opts.Capability,
		Model:       opts.Model,
		MaxTokens:   opts.MaxTokens,
		Temperature: opts.Temperature,
	}
	reply, err := s.client.Chat(ctx, prompt, merged)
	if err != nil {
		return "", err
	}
	s.append("user", prompt)
	s.append("assistant", reply)
	return reply, nil
}

// ChatStream sends one turn as a streaming request.
// Returns text chunks channel and error channel; consume text channel first.
func (s *Session) ChatStream(ctx context.Context, prompt string, opts *ChatOpts) (<-chan string, <-chan error) {
	if opts == nil {
		opts = &ChatOpts{}
	}
	merged := &ChatOpts{
		System:     s.system,
		History:    s.history,
		Capability: opts.Capability,
		Model:      opts.Model,
	}
	rawChunks, rawErr := s.client.ChatStream(ctx, prompt, merged)

	outChunks := make(chan string, 32)
	outErr := make(chan error, 1)

	go func() {
		defer close(outChunks)
		defer close(outErr)

		var sb strings.Builder
		for chunk := range rawChunks {
			sb.WriteString(chunk)
			outChunks <- chunk
		}
		if err := <-rawErr; err != nil {
			outErr <- err
			return
		}
		fullReply := sb.String()
		s.append("user", prompt)
		s.append("assistant", fullReply)
	}()

	return outChunks, outErr
}

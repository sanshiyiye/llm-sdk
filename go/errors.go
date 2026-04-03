// Package llmclient provides a unified LLM client for multiple providers.
package llmclient

import "fmt"

// LLMError is the base error type for all SDK errors.
type LLMError struct {
	Message    string
	StatusCode int
	Raw        string
}

func (e *LLMError) Error() string { return e.Message }

// RateLimitError is returned on HTTP 429. RetryAfter is in seconds.
type RateLimitError struct {
	LLMError
	RetryAfter float64
}

// TimeoutError is returned on request timeout.
type TimeoutError struct{ LLMError }

// ModelError is returned on HTTP 400/422 (bad request). Do not retry.
type ModelError struct{ LLMError }

// ProxyError is returned on HTTP 500/502/503/504. May be retried.
type ProxyError struct{ LLMError }

// AuthError is returned on HTTP 401/403. Do not retry.
type AuthError struct{ LLMError }

// NetworkError is returned on transport-level failures.
type NetworkError struct{ LLMError }

// StructuredOutputError is returned when JSON parsing fails.
type StructuredOutputError struct {
	LLMError
	RawResponse string
}

// TemplateNotFoundError is returned when a template name is unknown.
type TemplateNotFoundError struct {
	LLMError
	TemplateName string
}

// classifyError maps HTTP status codes to typed errors.
func classifyError(status int, body string) error {
	base := LLMError{StatusCode: status, Raw: body}
	switch {
	case status == 401 || status == 403:
		base.Message = "authentication failed"
		return &AuthError{base}
	case status == 429:
		base.Message = "rate limit exceeded"
		return &RateLimitError{LLMError: base, RetryAfter: 5}
	case status == 400 || status == 422:
		base.Message = fmt.Sprintf("model rejected request (HTTP %d)", status)
		return &ModelError{base}
	case status == 500 || status == 502 || status == 503 || status == 504:
		base.Message = fmt.Sprintf("proxy error (HTTP %d)", status)
		return &ProxyError{base}
	default:
		base.Message = fmt.Sprintf("HTTP %d", status)
		return &LLMError{Message: base.Message, StatusCode: status, Raw: body}
	}
}

// isRetryable returns true if the error warrants a retry attempt.
func isRetryable(err error) bool {
	switch err.(type) {
	case *AuthError, *ModelError:
		return false
	case *RateLimitError, *ProxyError, *TimeoutError, *NetworkError:
		return true
	default:
		return false
	}
}

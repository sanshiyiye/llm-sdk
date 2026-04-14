// Package llmclient - Doctor health check
// 用法：
//
//	result := c.Doctor(ctx)
//	result.Print()
//	if !result.OK { log.Fatal("LLM SDK 配置异常") }
package llmclient

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

// DoctorCheck is the result of a single health check.
type DoctorCheck struct {
	Name    string
	OK      bool
	Message string
	Fix     string // remediation hint, empty when OK=true
}

// DoctorResult holds all check results from Doctor().
type DoctorResult struct {
	Checks []DoctorCheck
}

// OK returns true if every check passed.
func (r *DoctorResult) OK() bool {
	for _, c := range r.Checks {
		if !c.OK {
			return false
		}
	}
	return true
}

// Print writes a human-readable diagnostic report to stdout.
func (r *DoctorResult) Print() {
	fmt.Println("LLM SDK Doctor")
	fmt.Println(strings.Repeat("=", 40))
	for _, c := range r.Checks {
		icon := "✓"
		if !c.OK {
			icon = "✗"
		}
		fmt.Printf("%s  %-22s %s\n", icon, c.Name, c.Message)
		if !c.OK && c.Fix != "" {
			fmt.Printf("   %-22s → %s\n", "", c.Fix)
		}
	}
	fmt.Println()
	if r.OK() {
		fmt.Println("全部通过，SDK 可正常使用。")
	} else {
		failed := 0
		for _, c := range r.Checks {
			if !c.OK {
				failed++
			}
		}
		fmt.Printf("%d 项检查未通过，请按上方提示修复。\n", failed)
	}
}

// Doctor runs all health checks and returns a DoctorResult.
// It is safe to call concurrently. Each check has a short timeout
// so Doctor returns quickly even when the Proxy is unreachable.
func (c *Client) Doctor(ctx context.Context) *DoctorResult {
	result := &DoctorResult{}
	httpClient := &http.Client{Timeout: 5 * time.Second}

	// ── 1. LLM_BASE_URL 是否配置 ─────────────────────────────────────────────
	envURL := os.Getenv("LLM_BASE_URL")
	if envURL != "" {
		result.Checks = append(result.Checks, DoctorCheck{
			Name:    "LLM_BASE_URL",
			OK:      true,
			Message: fmt.Sprintf("已配置 (%s)", c.BaseURL),
		})
	} else {
		result.Checks = append(result.Checks, DoctorCheck{
			Name:    "LLM_BASE_URL",
			OK:      false,
			Message: fmt.Sprintf("未设置，使用默认值 (%s)", c.BaseURL),
			Fix:     "export LLM_BASE_URL=https://your-proxy.example.com  （或启动本地 Proxy）",
		})
	}

	// ── 2. LLM_API_KEY 是否配置 ──────────────────────────────────────────────
	envKey := os.Getenv("LLM_API_KEY")
	if envKey != "" && envKey != "no-key" {
		result.Checks = append(result.Checks, DoctorCheck{
			Name:    "LLM_API_KEY",
			OK:      true,
			Message: "已配置",
		})
	} else {
		result.Checks = append(result.Checks, DoctorCheck{
			Name:    "LLM_API_KEY",
			OK:      false,
			Message: "未设置或使用占位值 'no-key'",
			Fix:     "export LLM_API_KEY=sk-your-team-key  （向平台团队申请）",
		})
	}

	// ── 3. Proxy 可达性检查 ───────────────────────────────────────────────────
	proxyReachable := false
	readinessURL := c.BaseURL + "/health/readiness"
	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, readinessURL, nil)
	resp, err := httpClient.Do(req)
	if err != nil {
		fix := "共享 Proxy：确认 LLM_BASE_URL 正确，检查网络/VPN\n   本地 Proxy：docker compose -f proxy/docker-compose.dev.yaml up -d"
		if strings.Contains(err.Error(), "timeout") || strings.Contains(err.Error(), "context deadline") {
			fix = "检查网络连接，确认 Proxy 地址可从本机访问"
		}
		result.Checks = append(result.Checks, DoctorCheck{
			Name:    "Proxy 可达",
			OK:      false,
			Message: fmt.Sprintf("连接失败 (%s): %v", c.BaseURL, err),
			Fix:     fix,
		})
	} else {
		resp.Body.Close()
		if resp.StatusCode < 500 {
			proxyReachable = true
			result.Checks = append(result.Checks, DoctorCheck{
				Name:    "Proxy 可达",
				OK:      true,
				Message: fmt.Sprintf("HTTP %d /health/readiness", resp.StatusCode),
			})
		} else {
			result.Checks = append(result.Checks, DoctorCheck{
				Name:    "Proxy 可达",
				OK:      false,
				Message: fmt.Sprintf("HTTP %d，Proxy 返回错误", resp.StatusCode),
				Fix:     "检查 Proxy 服务是否正常运行，查看 Proxy 日志",
			})
		}
	}

	// ── 4. 鉴权有效性 ─────────────────────────────────────────────────────────
	// 用 GET /models 验证 key，避免触发实际推理（不依赖具体模型是否可用）
	if proxyReachable {
		authReq, _ := http.NewRequestWithContext(ctx, http.MethodGet,
			c.BaseURL+"/models", nil)
		authReq.Header.Set("Authorization", "Bearer "+c.APIKey)
		authClient := &http.Client{Timeout: 10 * time.Second}
		authResp, err := authClient.Do(authReq)
		if err != nil {
			result.Checks = append(result.Checks, DoctorCheck{
				Name:    "鉴权有效",
				OK:      false,
				Message: fmt.Sprintf("请求失败: %v", err),
				Fix:     "确认 Proxy 可用后重试",
			})
		} else {
			io.Copy(io.Discard, authResp.Body)
			authResp.Body.Close()
			switch authResp.StatusCode {
			case 200, 201:
				result.Checks = append(result.Checks, DoctorCheck{
					Name:    "鉴权有效",
					OK:      true,
					Message: "API key 验证成功",
				})
			case 401, 403:
				result.Checks = append(result.Checks, DoctorCheck{
					Name:    "鉴权有效",
					OK:      false,
					Message: fmt.Sprintf("HTTP %d 鉴权失败", authResp.StatusCode),
					Fix:     "检查 LLM_API_KEY 是否与 Proxy 端 LITELLM_MASTER_KEY 一致，向平台团队确认",
				})
			default:
				result.Checks = append(result.Checks, DoctorCheck{
					Name:    "鉴权有效",
					OK:      false,
					Message: fmt.Sprintf("HTTP %d", authResp.StatusCode),
					Fix:     "查看 Proxy 日志了解详情",
				})
			}
		}
	} else {
		result.Checks = append(result.Checks, DoctorCheck{
			Name:    "鉴权有效",
			OK:      false,
			Message: "跳过（Proxy 不可达）",
			Fix:     "先修复 Proxy 可达性问题",
		})
	}

	// ── 5. Capability override 合理性检查 ────────────────────────────────────
	// 含 / 是合法 provider/model 格式；含 - 是 Proxy 内部别名，两者都允许。
	// 没有 / 也没有 - 的短名才可能是错误格式。
	tagEnvMap := map[string]string{
		"chat":        "LLM_MODEL_CHAT",
		"vision":      "LLM_MODEL_VISION",
		"video-input": "LLM_MODEL_VIDEO",
		"embedding":   "LLM_MODEL_EMBEDDING",
		"image-gen":   "LLM_MODEL_IMAGE_GEN",
		"fast":        "LLM_MODEL_FAST",
		"local":       "LLM_MODEL_LOCAL",
	}
	overrideIssues := 0
	for tag, envKeyName := range tagEnvMap {
		_ = tag
		envVal := os.Getenv(envKeyName)
		if envVal != "" && !strings.Contains(envVal, "/") && !strings.Contains(envVal, "-") {
			overrideIssues++
		}
	}

	if overrideIssues > 0 {
		result.Checks = append(result.Checks, DoctorCheck{
			Name:    "Capability 配置",
			OK:      false,
			Message: fmt.Sprintf("发现 %d 个可能有问题的覆盖", overrideIssues),
			Fix:     "模型名建议使用 provider/model 格式，如 openai/gpt-4o 或使用默认值",
		})
	} else {
		result.Checks = append(result.Checks, DoctorCheck{
			Name:    "Capability 配置",
			OK:      true,
			Message: fmt.Sprintf("%d 个 tag 配置正常", len(c.TagMap)),
		})
	}

	return result
}

// LLM SDK Go Starter
// ===================
// 新项目接入 LLM SDK 的最小示例。
//
// 使用步骤：
// 1. go mod tidy
// 2. 配置环境变量（见 .env.example）
// 3. go run main.go
// 4. 遇到问题：go run main.go -doctor
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"

	llmclient "github.com/goat/llm-sdk/sdk/go"
)

func main() {
	doctorMode := flag.Bool("doctor", false, "运行健康检查诊断")
	flag.Parse()

	c := llmclient.New()
	ctx := context.Background()

	if *doctorMode {
		result := c.Doctor(ctx)
		result.Print()
		if !result.OK() {
			os.Exit(1)
		}
		return
	}

	// 启动前快速健康检查
	result := c.Doctor(ctx)
	if !result.OK() {
		fmt.Println("⚠️  SDK 配置检查未全部通过，尝试运行示例...\n")
	}

	runExamples(ctx, c)
}

func runExamples(ctx context.Context, c *llmclient.Client) {
	// ── 基础对话 ──────────────────────────────────────────────────────────────
	fmt.Println("=== 基础对话 ===")
	reply, err := c.Chat(ctx, "用一句话介绍 Go 语言", nil)
	if err != nil {
		log.Fatalf("chat 失败: %v", err)
	}
	fmt.Println(reply)
	fmt.Println()

	// ── 快速模型 ──────────────────────────────────────────────────────────────
	fmt.Println("=== 快速模型 ===")
	fast, err := c.Chat(ctx, "1+1=?", &llmclient.ChatOpts{Capability: "fast"})
	if err != nil {
		log.Printf("fast chat 失败: %v", err)
	} else {
		fmt.Println(fast)
	}
	fmt.Println()

	// ── 流式输出 ──────────────────────────────────────────────────────────────
	fmt.Println("=== 流式输出 ===")
	chunks, errc := c.ChatStream(ctx, "用三句话介绍大语言模型", nil)
	for chunk := range chunks {
		fmt.Print(chunk)
	}
	if err := <-errc; err != nil {
		log.Printf("stream 错误: %v", err)
	}
	fmt.Println()
	fmt.Println()

	// ── 结构化输出 ────────────────────────────────────────────────────────────
	fmt.Println("=== 结构化输出 ===")
	type Summary struct {
		Title  string   `json:"title"`
		Points []string `json:"points"`
	}
	var summary Summary
	if err := c.ChatStructured(ctx, "总结 Go 语言的三大优点，返回 title 和 points 列表", &summary, nil); err != nil {
		log.Printf("structured 失败: %v", err)
	} else {
		fmt.Printf("标题: %s\n", summary.Title)
		for _, p := range summary.Points {
			fmt.Printf("  - %s\n", p)
		}
	}
	fmt.Println()

	// ── 多轮会话 ──────────────────────────────────────────────────────────────
	fmt.Println("=== 多轮会话 ===")
	sess := c.NewSession("你是一个简洁的编程助手，每次回答不超过两句话")
	r1, err := sess.Chat(ctx, "什么是 goroutine？", nil)
	if err != nil {
		log.Printf("session chat 失败: %v", err)
	} else {
		fmt.Printf("Q1 回答: %s\n", r1)
	}
	r2, err := sess.Chat(ctx, "给一个简单例子", nil)
	if err != nil {
		log.Printf("session chat 失败: %v", err)
	} else {
		fmt.Printf("Q2 回答: %s\n", r2)
	}
}

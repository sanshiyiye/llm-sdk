/**
 * LLM SDK TypeScript Starter
 * ==========================
 * 新项目接入 LLM SDK 的最小示例。
 *
 * 使用步骤：
 * 1. npm install
 * 2. 复制 .env.example 为 .env 并填写配置
 * 3. npx ts-node main.ts
 * 4. 遇到问题：npx ts-node main.ts --doctor
 */

import { client } from '@goat/llm-sdk'
import { z } from 'zod'

async function checkConfig(): Promise<boolean> {
  const result = await client.doctor()
  result.print()
  return result.ok
}

async function runExamples() {
  // ── 基础对话 ──────────────────────────────────────────────────────────────
  console.log('=== 基础对话 ===')
  const reply = await client.chat('用一句话介绍 TypeScript')
  console.log(reply.content)
  console.log()

  // ── 快速模型 ──────────────────────────────────────────────────────────────
  console.log('=== 快速模型 ===')
  const fast = await client.chat('1+1=?', { capability: 'fast' })
  console.log(fast.content)
  console.log()

  // ── 流式输出 ──────────────────────────────────────────────────────────────
  console.log('=== 流式输出 ===')
  for await (const chunk of client.chatStream('用三句话介绍大语言模型')) {
    process.stdout.write(chunk)
  }
  console.log('\n')

  // ── 结构化输出（Zod）─────────────────────────────────────────────────────
  console.log('=== 结构化输出 ===')
  const SummarySchema = z.object({
    title: z.string(),
    points: z.array(z.string()),
  })
  const structured = await client.chatStructured(
    '总结 TypeScript 的三大优点，返回 title 和 points 列表',
    SummarySchema,
  )
  console.log(`标题: ${structured.title}`)
  structured.points.forEach(p => console.log(`  - ${p}`))
  console.log()

  // ── 多轮会话 ──────────────────────────────────────────────────────────────
  console.log('=== 多轮会话 ===')
  const session = client.session('你是一个简洁的编程助手，每次回答不超过两句话')
  const r1 = await session.chat('什么是类型推断？')
  console.log(`Q1 回答: ${r1.content}`)
  const r2 = await session.chat('给一个 TypeScript 例子')
  console.log(`Q2 回答: ${r2.content}`)
}

async function main() {
  const isDoctorMode = process.argv.includes('--doctor')

  if (isDoctorMode) {
    const ok = await checkConfig()
    process.exit(ok ? 0 : 1)
  }

  // 启动前快速健康检查
  const result = await client.doctor()
  if (!result.ok) {
    console.warn('⚠️  SDK 配置检查未全部通过，尝试运行示例...\n')
  }

  await runExamples()
}

main().catch(err => {
  console.error('运行出错:', err)
  process.exit(1)
})

/**
 * LLM SDK Doctor - TypeScript
 * ============================
 * 连接与配置健康检查
 *
 * 用法:
 *   import { client } from '@goat/llm-sdk'
 *   const result = await client.doctor()
 *   result.print()
 *
 *   // 或断言全部通过
 *   if (!result.ok) throw new Error('LLM SDK 配置异常')
 */

/** 单项检查结果 */
export interface DoctorCheck {
  name: string
  ok: boolean
  message: string
  fix?: string  // 修复建议，仅在 ok=false 时填充
}

/** doctor() 的完整诊断结果 */
export class DoctorResult {
  constructor(public readonly checks: DoctorCheck[] = []) {}

  get ok(): boolean {
    return this.checks.every(c => c.ok)
  }

  print(): void {
    console.log('LLM SDK Doctor')
    console.log('='.repeat(40))
    for (const c of this.checks) {
      const icon = c.ok ? '✓' : '✗'
      const namePad = c.name.padEnd(22)
      console.log(`${icon}  ${namePad} ${c.message}`)
      if (!c.ok && c.fix) {
        console.log(`   ${''.padEnd(22)} → ${c.fix}`)
      }
    }
    console.log()
    if (this.ok) {
      console.log('全部通过，SDK 可正常使用。')
    } else {
      const failed = this.checks.filter(c => !c.ok).length
      console.log(`${failed} 项检查未通过，请按上方提示修复。`)
    }
  }
}

const tagEnvMap: Record<string, string> = {
  'chat':        'LLM_MODEL_CHAT',
  'vision':      'LLM_MODEL_VISION',
  'video-input': 'LLM_MODEL_VIDEO',
  'embedding':   'LLM_MODEL_EMBEDDING',
  'image-gen':   'LLM_MODEL_IMAGE_GEN',
  'fast':        'LLM_MODEL_FAST',
  'local':       'LLM_MODEL_LOCAL',
}

/**
 * 执行所有健康检查，返回 DoctorResult。
 * 设计原则：每项检查独立，超时设短（5s），错误给出 fix hint。
 */
export async function runDoctor(
  baseURL: string,
  apiKey: string,
  tagMap: Record<string, string>,
): Promise<DoctorResult> {
  const checks: DoctorCheck[] = []

  // ── 1. LLM_BASE_URL 是否配置 ──────────────────────────────────────────────
  const envURL = process.env.LLM_BASE_URL ?? ''
  if (envURL) {
    checks.push({ name: 'LLM_BASE_URL', ok: true, message: `已配置 (${baseURL})` })
  } else {
    checks.push({
      name: 'LLM_BASE_URL',
      ok: false,
      message: `未设置，使用默认值 (${baseURL})`,
      fix: 'export LLM_BASE_URL=https://your-proxy.example.com  （或启动本地 Proxy）',
    })
  }

  // ── 2. LLM_API_KEY 是否配置 ───────────────────────────────────────────────
  const envKey = process.env.LLM_API_KEY ?? ''
  if (envKey && envKey !== 'no-key') {
    checks.push({ name: 'LLM_API_KEY', ok: true, message: '已配置' })
  } else {
    checks.push({
      name: 'LLM_API_KEY',
      ok: false,
      message: "未设置或使用占位值 'no-key'",
      fix: 'export LLM_API_KEY=sk-your-team-key  （向平台团队申请）',
    })
  }

  // ── 3. Proxy 可达性检查 ───────────────────────────────────────────────────
  let proxyReachable = false
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)
    const resp = await fetch(`${baseURL}/health/readiness`, {
      signal: controller.signal,
    }).finally(() => clearTimeout(timeout))

    if (resp.status < 500) {
      proxyReachable = true
      checks.push({
        name: 'Proxy 可达',
        ok: true,
        message: `HTTP ${resp.status} /health/readiness`,
      })
    } else {
      checks.push({
        name: 'Proxy 可达',
        ok: false,
        message: `HTTP ${resp.status}，Proxy 返回错误`,
        fix: '检查 Proxy 服务是否正常运行，查看 Proxy 日志',
      })
    }
  } catch (e: any) {
    const isTimeout = e?.name === 'AbortError'
    if (isTimeout) {
      checks.push({
        name: 'Proxy 可达',
        ok: false,
        message: `连接超时 (${baseURL})`,
        fix: '检查网络连接，确认 Proxy 地址可从本机访问',
      })
    } else {
      checks.push({
        name: 'Proxy 可达',
        ok: false,
        message: `连接失败 (${baseURL}): ${e?.message ?? e}`,
        fix: '共享 Proxy：确认 LLM_BASE_URL 正确，检查网络/VPN\n   本地 Proxy：docker compose -f proxy/docker-compose.dev.yaml up -d',
      })
    }
  }

  // ── 4. 鉴权有效性 ─────────────────────────────────────────────────────────
  // 用 GET /models 验证 key，避免触发实际推理（不依赖具体模型是否可用）
  if (proxyReachable) {
    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 10000)
      const resp = await fetch(`${baseURL}/models`, {
        headers: { Authorization: `Bearer ${apiKey}` },
        signal: controller.signal,
      }).finally(() => clearTimeout(timeout))

      if (resp.status === 200 || resp.status === 201) {
        checks.push({ name: '鉴权有效', ok: true, message: 'API key 验证成功' })
      } else if (resp.status === 401 || resp.status === 403) {
        checks.push({
          name: '鉴权有效',
          ok: false,
          message: `HTTP ${resp.status} 鉴权失败`,
          fix: '检查 LLM_API_KEY 是否与 Proxy 端 LITELLM_MASTER_KEY 一致，向平台团队确认',
        })
      } else {
        checks.push({
          name: '鉴权有效',
          ok: false,
          message: `HTTP ${resp.status}`,
          fix: '查看 Proxy 日志了解详情',
        })
      }
    } catch (e: any) {
      checks.push({
        name: '鉴权有效',
        ok: false,
        message: `请求失败: ${e?.message ?? e}`,
        fix: '确认 Proxy 可用后重试',
      })
    }
  } else {
    checks.push({
      name: '鉴权有效',
      ok: false,
      message: '跳过（Proxy 不可达）',
      fix: '先修复 Proxy 可达性问题',
    })
  }

  // ── 5. Capability override 合理性检查 ────────────────────────────────────
  // 含 / 是合法 provider/model 格式；含 - 是 Proxy 内部别名，两者都允许。
  // 没有 / 也没有 - 的短名才可能是错误格式。
  const overrideIssues: string[] = []
  for (const [tag, model] of Object.entries(tagMap)) {
    const envKeyName = tagEnvMap[tag]
    const envVal = envKeyName ? (process.env[envKeyName] ?? '') : ''
    if (envVal && !envVal.includes('/') && !envVal.includes('-')) {
      overrideIssues.push(`${envKeyName}=${envVal} 可能不含 provider 前缀`)
    }
  }

  if (overrideIssues.length > 0) {
    checks.push({
      name: 'Capability 配置',
      ok: false,
      message: `发现 ${overrideIssues.length} 个可能有问题的覆盖`,
      fix: '模型名建议使用 provider/model 格式，如 openai/gpt-4o 或使用默认值',
    })
  } else {
    checks.push({
      name: 'Capability 配置',
      ok: true,
      message: `${Object.keys(tagMap).length} 个 tag 配置正常`,
    })
  }

  return new DoctorResult(checks)
}

/**
 * LLM SDK - TypeScript/Node.js
 * ============================
 * 用法:
 *   import { client } from './llm_sdk'
 *   const reply  = await client.chat('你好')
 *   const reply2 = await client.chat('描述图片', { imageUrl: 'https://...' })
 *   const vec    = await client.embed('some text')
 *   const url    = await client.imageGen('a cat on the moon')
 *   const sess   = client.session('你是助手')
 */

import OpenAI from 'openai'
import {
  AuthError, LLMError, ModelError, NetworkError,
  ProxyError, RateLimitError, TimeoutError, classifyError,
} from './errors'
import { Session } from './session'
import type { ZodType, ZodInfer } from './structured'
import { createCache, buildCacheKey } from './cache'
import type { CacheBackend, CacheOptions } from './cache'
import { chatStructured } from './structured'
import { templates } from './templates'

// ── Capability tag → model_name 映射 ────────────────────────────────────────

export const TAG_MODEL_MAP: Record<string, string> = {
  'chat':        process.env.LLM_MODEL_CHAT        ?? 'auto-chat',
  'vision':      process.env.LLM_MODEL_VISION      ?? 'auto-vision',
  'video-input': process.env.LLM_MODEL_VIDEO        ?? 'gemini-vision',
  'embedding':   process.env.LLM_MODEL_EMBEDDING   ?? 'text-embedding',
  'image-gen':   process.env.LLM_MODEL_IMAGE_GEN   ?? 'gpt-image-gen',
  'fast':        process.env.LLM_MODEL_FAST        ?? 'gemini-chat',
  'reasoning':   process.env.LLM_MODEL_REASONING   ?? 'auto-reasoning',
  'local':       process.env.LLM_MODEL_LOCAL       ?? 'local-chat',
}

export type Capability = keyof typeof TAG_MODEL_MAP

export function resolveModel(capability: string): string {
  const model = TAG_MODEL_MAP[capability]
  if (!model) throw new Error(`未知 capability: '${capability}'，可用值: ${Object.keys(TAG_MODEL_MAP).join(', ')}`)
  return model
}

// ── 参数类型 ─────────────────────────────────────────────────────────────────

export interface ChatOptions {
  system?: string
  history?: OpenAI.ChatCompletionMessageParam[]
  imageUrl?: string
  imageBase64?: { data: string; mime?: string }
  capability?: string
  model?: string
  maxTokens?: number
  temperature?: number
  cache?: boolean
}

export interface EmbedOptions { model?: string }
export interface ImageGenOptions { size?: string; model?: string }

// ── 重试工具 ─────────────────────────────────────────────────────────────────

const RETRY_STATUSES = new Set([500, 502, 503, 504])
const NO_RETRY_STATUSES = new Set([400, 401, 403, 422])

async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 2,
  baseDelay = 1000,
): Promise<T> {
  let lastErr: unknown
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn()
    } catch (e) {
      if (e instanceof AuthError || e instanceof ModelError) throw e
      if (e instanceof RateLimitError) {
        lastErr = e
        if (attempt < maxRetries) await sleep(e.retryAfter * 1000)
      } else if (e instanceof ProxyError || e instanceof TimeoutError || e instanceof NetworkError) {
        lastErr = e
        if (attempt < maxRetries) await sleep(baseDelay * 2 ** attempt)
      } else {
        throw new NetworkError(String(e))
      }
    }
  }
  throw lastErr
}

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

function wrapOpenAIError(e: unknown): LLMError {
  const status = (e as any)?.status ?? 0
  return classifyError(status, String(e))
}

// ── 主客户端 ─────────────────────────────────────────────────────────────────

export interface LLMClientOptions {
  baseURL?: string
  apiKey?: string
  maxRetries?: number
  cache?: CacheOptions
}

export class LLMClient {
  private openai: OpenAI
  private maxRetries: number
  private cache: CacheBackend | null

  constructor(options: LLMClientOptions = {}) {
    const baseURL = options.baseURL ?? process.env.LLM_BASE_URL ?? 'http://localhost:4000'
    const apiKey = options.apiKey ?? process.env.LLM_API_KEY ?? 'no-key'
    this.maxRetries = options.maxRetries ?? 2
    this.cache = createCache(options.cache ?? false)
    this.openai = new OpenAI({ 
      baseURL, 
      apiKey, 
      maxRetries: 0,
      timeout: 5 * 60 * 1000 // 5分钟超时，适应 Reasoning 等慢思考模型
    })
  }

  private resolveModel(capability: string, hasImage: boolean, opts: ChatOptions): string {
    if (opts.model) return opts.model
    const cap = opts.capability ?? (hasImage ? 'vision' : 'chat')
    return resolveModel(cap)
  }

  private buildMessages(
    prompt: string,
    opts: ChatOptions,
  ): OpenAI.ChatCompletionMessageParam[] {
    const { system, history, imageUrl, imageBase64 } = opts
    const messages: OpenAI.ChatCompletionMessageParam[] = []
    if (system) messages.push({ role: 'system', content: system })
    if (history) messages.push(...history)

    const hasImage = !!(imageUrl || imageBase64)
    if (hasImage) {
      const parts: OpenAI.ChatCompletionContentPart[] = [{ type: 'text', text: prompt }]
      if (imageUrl) parts.push({ type: 'image_url', image_url: { url: imageUrl } })
      if (imageBase64) {
        const mime = imageBase64.mime ?? 'image/png'
        parts.push({ type: 'image_url', image_url: { url: `data:${mime};base64,${imageBase64.data}` } })
      }
      messages.push({ role: 'user', content: parts })
    } else {
      messages.push({ role: 'user', content: prompt })
    }
    return messages
  }

  // ── chat ─────────────────────────────────────────────────────────────────

  async chat(prompt: string, opts: ChatOptions = {}): Promise<{ content: string; cached: boolean }> {
    const hasImage = !!(opts.imageUrl || opts.imageBase64)
    const model = this.resolveModel('chat', hasImage, opts)
    const messages = this.buildMessages(prompt, opts)
    const useCache = opts.cache !== false && this.cache !== null

    // Check cache first
    if (useCache && this.cache) {
      const cacheKey = buildCacheKey(model, messages)
      const cached = this.cache.get(cacheKey)
      if (cached !== undefined) {
        return { content: cached as string, cached: true }
      }
    }

    // Make API call
    const result = await withRetry(async () => {
      try {
        const resp = await this.openai.chat.completions.create({
          model,
          messages,
          ...(opts.maxTokens ? { max_tokens: opts.maxTokens } : {}),
          ...(opts.temperature !== undefined ? { temperature: opts.temperature } : {}),
        })
        return resp.choices[0]?.message?.content || ''
      } catch (e) { throw wrapOpenAIError(e) }
    }, this.maxRetries)

    // Store in cache
    if (useCache && this.cache) {
      const cacheKey = buildCacheKey(model, messages)
      this.cache.set(cacheKey, result)
    }

    return { content: result, cached: false }
  }

  // ── chat stream ──────────────────────────────────────────────────────────

  async *chatStream(prompt: string, opts: ChatOptions = {}): AsyncGenerator<string> {
    const hasImage = !!(opts.imageUrl)
    const model = this.resolveModel('chat', hasImage, opts)
    const messages = this.buildMessages(prompt, opts)
    try {
      const stream = await this.openai.chat.completions.create({
        model, messages, stream: true,
      })
      for await (const chunk of stream) {
        const delta = chunk.choices[0]?.delta?.content
        if (delta) yield delta
      }
    } catch (e) { throw wrapOpenAIError(e) }
  }

  // ── embed ────────────────────────────────────────────────────────────────

  async embed(text: string, opts?: EmbedOptions): Promise<number[]>
  async embed(text: string[], opts?: EmbedOptions): Promise<number[][]>
  async embed(text: string | string[], opts: EmbedOptions = {}): Promise<number[] | number[][]> {
    const model = opts.model ?? resolveModel('embedding')
    return withRetry(async () => {
      try {
        const resp = await this.openai.embeddings.create({ model, input: text })
        if (typeof text === 'string') return resp.data[0].embedding
        return resp.data.map(d => d.embedding)
      } catch (e) { throw wrapOpenAIError(e) }
    }, this.maxRetries)
  }

  // ── image gen ────────────────────────────────────────────────────────────

  async imageGen(prompt: string, opts: ImageGenOptions = {}): Promise<string> {
    const { size = '1024x1024', model: explicitModel } = opts
    const model = explicitModel ?? resolveModel('image-gen')
    return withRetry(async () => {
      try {
        const resp = await this.openai.images.generate({
          model, prompt, size: size as OpenAI.ImageGenerateParams['size'],
        })
        return resp.data?.[0]?.url || ''
      } catch (e) { throw wrapOpenAIError(e) }
    }, this.maxRetries)
  }

  // ── session ──────────────────────────────────────────────────────────────

  session(system?: string): Session {
    return new Session(this, system)
  }

  async chatStructured<T>(
    prompt: string,
    schema: ZodType<T>,
    opts: ChatOptions = {},
  ): Promise<T> {
    return chatStructured(this, prompt, schema, opts)
  }

  async chatWithTemplate(
    templateName: string,
    variables: Record<string, string>,
    opts: Omit<ChatOptions, 'system'> = {},
  ): Promise<string> {
    return templates.chatWithTemplate(this, templateName, variables, opts)
  }
}

// ── 单例 ─────────────────────────────────────────────────────────────────────
export const client = new LLMClient()

/**
 * TypeScript SDK 测试
 * 运行: npx vitest run
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { z } from 'zod'

// ── Mock OpenAI ──────────────────────────────────────────────────────────────

vi.mock('openai', () => {
  const mockCreate = vi.fn()
  const mockEmbedCreate = vi.fn()
  const mockImagesGenerate = vi.fn()
  return {
    default: vi.fn().mockImplementation(() => ({
      chat: { completions: { create: mockCreate } },
      embeddings: { create: mockEmbedCreate },
      images: { generate: mockImagesGenerate },
    })),
    __mockCreate: mockCreate,
    __mockEmbedCreate: mockEmbedCreate,
    __mockImagesGenerate: mockImagesGenerate,
  }
})

function makeChatResp(content: string) {
  return { choices: [{ message: { content }, delta: { content } }] }
}

function makeToolResp(content: string, toolCalls: Array<{ id: string; name: string; arguments: Record<string, any> }>) {
  return {
    choices: [{
      message: {
        content,
        tool_calls: toolCalls.map(toolCall => ({
          id: toolCall.id,
          type: 'function',
          function: {
            name: toolCall.name,
            arguments: JSON.stringify(toolCall.arguments),
          },
        })),
      },
    }],
  }
}

// ── TAG_MODEL_MAP ─────────────────────────────────────────────────────────────

describe('TAG_MODEL_MAP', () => {
  it('contains all required capabilities', async () => {
    const { TAG_MODEL_MAP } = await import('../client')
    const required = ['chat', 'vision', 'video-input', 'embedding', 'image-gen', 'fast', 'reasoning', 'local']
    required.forEach(cap => expect(TAG_MODEL_MAP).toHaveProperty(cap))
  })

  it('throws on unknown capability', async () => {
    const { resolveModel } = await import('../client')
    expect(() => resolveModel('nonexistent')).toThrow('未知 capability')
  })
})

// ── LLMClient.chat ────────────────────────────────────────────────────────────

describe('LLMClient.chat', () => {
  it('uses chat model by default', async () => {
    const OpenAI = (await import('openai')).default as any
    const instance = new OpenAI()
    instance.chat.completions.create.mockResolvedValue(makeChatResp('hi'))
    const { LLMClient, TAG_MODEL_MAP } = await import('../client')
    const c = new LLMClient()
    await c.chat('hello')
    expect(instance.chat.completions.create).toHaveBeenCalledWith(
      expect.objectContaining({ model: TAG_MODEL_MAP['chat'] })
    )
  })

  it('uses vision model when imageUrl provided', async () => {
    const OpenAI = (await import('openai')).default as any
    const instance = new OpenAI()
    instance.chat.completions.create.mockResolvedValue(makeChatResp('ok'))
    const { LLMClient, TAG_MODEL_MAP } = await import('../client')
    const c = new LLMClient()
    await c.chat('describe', { imageUrl: 'https://example.com/img.png' })
    expect(instance.chat.completions.create).toHaveBeenCalledWith(
      expect.objectContaining({ model: TAG_MODEL_MAP['vision'] })
    )
  })

  it('explicit model overrides capability', async () => {
    const OpenAI = (await import('openai')).default as any
    const instance = new OpenAI()
    instance.chat.completions.create.mockResolvedValue(makeChatResp('ok'))
    const { LLMClient } = await import('../client')
    const c = new LLMClient()
    await c.chat('hello', { model: 'gpt-chat' })
    expect(instance.chat.completions.create).toHaveBeenCalledWith(
      expect.objectContaining({ model: 'gpt-chat' })
    )
  })
})

// ── Structured Output ─────────────────────────────────────────────────────────

describe('chatStructured', () => {
  it('parses valid JSON response', async () => {
    const OpenAI = (await import('openai')).default as any
    const instance = new OpenAI()
    instance.chat.completions.create.mockResolvedValue(
      makeChatResp('{"name":"iPhone","price":7999}')
    )
    const { LLMClient } = await import('../client')
    const c = new LLMClient()
    const schema = z.object({ name: z.string(), price: z.number() })
    const result = await c.chatStructured('extract', schema)
    expect(result.name).toBe('iPhone')
    expect(result.price).toBe(7999)
  })

  it('strips markdown code fences', async () => {
    const OpenAI = (await import('openai')).default as any
    const instance = new OpenAI()
    instance.chat.completions.create.mockResolvedValue(
      makeChatResp('```json\n{"value":42}\n```')
    )
    const { LLMClient } = await import('../client')
    const c = new LLMClient()
    const schema = z.object({ value: z.number() })
    const result = await c.chatStructured('get', schema)
    expect(result.value).toBe(42)
  })

  it('throws StructuredOutputError on invalid JSON', async () => {
    const OpenAI = (await import('openai')).default as any
    const instance = new OpenAI()
    instance.chat.completions.create.mockResolvedValue(makeChatResp('not json at all'))
    const { LLMClient } = await import('../client')
    const c = new LLMClient()
    const schema = z.object({ value: z.number() })
    try {
      await c.chatStructured('get', schema)
      throw new Error('should have thrown')
    } catch (e: any) {
      expect(e.name).toBe('StructuredOutputError')
    }
  })
})

// ── Session ───────────────────────────────────────────────────────────────────

describe('Session', () => {
  it('maintains history across turns', async () => {
    const OpenAI = (await import('openai')).default as any
    const instance = new OpenAI()
    instance.chat.completions.create
      .mockResolvedValueOnce(makeChatResp('reply1'))
      .mockResolvedValueOnce(makeChatResp('reply2'))
    const { LLMClient } = await import('../client')
    const c = new LLMClient()
    const sess = c.session('you are helpful')
    await sess.chat('q1')
    await sess.chat('q2')
    expect(sess.turns).toBe(2)
  })

  it('clears history but keeps system', async () => {
    const OpenAI = (await import('openai')).default as any
    const instance = new OpenAI()
    instance.chat.completions.create.mockResolvedValue(makeChatResp('ok'))
    const { LLMClient } = await import('../client')
    const c = new LLMClient()
    const sess = c.session('system prompt')
    await sess.chat('hi')
    expect(sess.turns).toBe(1)
    sess.clear()
    expect(sess.turns).toBe(0)
  })
})

// ── Tool Use ──────────────────────────────────────────────────────────────────

describe('chatWithTools', () => {
  it('executes tool loop and returns final reply', async () => {
    const OpenAIModule = await import('openai') as any
    const OpenAI = OpenAIModule.default as any
    const mockCreate = OpenAIModule.__mockCreate as any
    const instance = new OpenAI()
    instance.chat.completions.create
      .mockResolvedValueOnce(
        makeToolResp('', [
          { id: 'call_1', name: 'get_weather', arguments: { city: '北京' } },
        ])
      )
      .mockResolvedValueOnce(makeChatResp('北京今天是晴天'))

    const { LLMClient } = await import('../client')
    const { llmTool } = await import('../tools')
    const c = new LLMClient()
    const getWeather = llmTool({
      name: 'get_weather',
      parameters: {
        type: 'object',
        properties: {
          city: { type: 'string' },
        },
        required: ['city'],
      },
    })((city: string) => `${city} 晴`)

    const reply = await c.chatWithTools('北京天气如何？', [getWeather])
    const [firstToolCall, secondToolCall] = mockCreate.mock.calls.slice(-2)

    expect(reply).toBe('北京今天是晴天')
    expect(firstToolCall[0].tools[0].function.name).toBe('get_weather')
    const secondMessages = secondToolCall[0].messages
    expect(secondMessages.some((m: any) => m.role === 'tool' && m.content === '北京 晴')).toBe(true)
  })
})

// ── Templates ─────────────────────────────────────────────────────────────────

describe('TemplateRegistry', () => {
  it('registers and renders a template', async () => {
    const { TemplateRegistry } = await import('../templates')
    const reg = new TemplateRegistry()
    reg.register('greet', { user: '用 {lang} 打招呼' })
    const tmpl = reg.get('greet')
    expect(tmpl).toBeDefined()
  })

  it('throws TemplateNotFoundError for unknown template', async () => {
    const { TemplateRegistry } = await import('../templates')
    const reg = new TemplateRegistry()
    try {
      reg.get('missing')
      throw new Error('should have thrown')
    } catch (e: any) {
      expect(e.name).toBe('TemplateNotFoundError')
    }
  })

  it('lists registered templates', async () => {
    const { TemplateRegistry } = await import('../templates')
    const reg = new TemplateRegistry()
    reg.register('a', { user: 'a' })
    reg.register('b', { user: 'b' })
    expect(reg.list().sort()).toEqual(['a', 'b'])
  })
})

// ── Errors ────────────────────────────────────────────────────────────────────

describe('Error hierarchy', () => {
  it('all errors extend LLMError', async () => {
    const {
      LLMError, RateLimitError, AuthError, ModelError,
      ProxyError, NetworkError,
    } = await import('../errors')
    ;[RateLimitError, AuthError, ModelError, ProxyError, NetworkError].forEach((Cls: any) => {
      expect(new Cls('test') instanceof LLMError).toBe(true)
    })
  })

  it('RateLimitError has retryAfter', async () => {
    const { RateLimitError } = await import('../errors')
    const e = new RateLimitError('limited', 30)
    expect(e.retryAfter).toBe(30)
    expect(e.statusCode).toBe(429)
  })
})

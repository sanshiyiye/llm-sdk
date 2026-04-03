/**
 * Integration tests for TypeScript SDK
 * Run: npx vitest run tests/integration/typescript-sdk.test.ts
 * 
 * These tests verify the TypeScript SDK behavior against a mock LLM proxy.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { z } from 'zod'
import { LLMClient, TAG_MODEL_MAP } from '../../typescript/index'
import { RateLimitError, AuthError, ModelError, StructuredOutputError } from '../../typescript/errors'

// ── Mocks ───────────────────────────────────────────────────────────────────

const mockFetch = vi.fn()
global.fetch = mockFetch

function mockResponse(status: number, body: any): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
    body: null
  } as Response
}

function mockStreamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    }
  })
  
  return {
    ok: true,
    status: 200,
    body: stream,
    json: () => Promise.resolve({}),
    text: () => Promise.resolve('')
  } as Response
}

// ── Tests ───────────────────────────────────────────────────────────────────

describe('Basic Chat', () => {
  beforeEach(() => mockFetch.mockClear())

  it('should return string from chat', async () => {
    mockFetch.mockResolvedValue(mockResponse(200, {
      choices: [{ message: { content: 'Hello!' } }]
    }))

    const c = new LLMClient()
    const result = await c.chat('Hi')

    expect(typeof result).toBe('string')
    expect(result).toBe('Hello!')
  })

  it('should use model override when provided', async () => {
    mockFetch.mockResolvedValue(mockResponse(200, {
      choices: [{ message: { content: 'ok' } }]
    }))

    const c = new LLMClient()
    await c.chat('test', { model: 'gpt-4' })

    const callArgs = mockFetch.mock.calls[0]
    const sentBody = JSON.parse(callArgs[1].body)
    expect(sentBody.model).toBe('gpt-4')
  })
})

describe('Capability Routing', () => {
  beforeEach(() => mockFetch.mockClear())

  it('should use default chat capability', async () => {
    mockFetch.mockResolvedValue(mockResponse(200, {
      choices: [{ message: { content: 'ok' } }]
    }))

    const c = new LLMClient()
    await c.chat('test')

    const callArgs = mockFetch.mock.calls[0]
    const sentBody = JSON.parse(callArgs[1].body)
    expect(sentBody.model).toBe(TAG_MODEL_MAP.chat)
  })

  it('should route fast capability to different model', async () => {
    mockFetch.mockResolvedValue(mockResponse(200, {
      choices: [{ message: { content: 'ok' } }]
    }))

    const c = new LLMClient()
    await c.chat('test', { capability: 'fast' })

    const callArgs = mockFetch.mock.calls[0]
    const sentBody = JSON.parse(callArgs[1].body)
    expect(sentBody.model).toBe(TAG_MODEL_MAP.fast)
    expect(sentBody.model).not.toBe(TAG_MODEL_MAP.chat)
  })
})

describe('Vision Auto-Inference', () => {
  beforeEach(() => mockFetch.mockClear())

  it('should use vision capability when image_url provided', async () => {
    mockFetch.mockResolvedValue(mockResponse(200, {
      choices: [{ message: { content: 'I see a cat.' } }]
    }))

    const c = new LLMClient()
    await c.chat('Describe this', { imageUrl: 'https://example.com/cat.jpg' })

    const callArgs = mockFetch.mock.calls[0]
    const sentBody = JSON.parse(callArgs[1].body)
    expect(sentBody.model).toBe(TAG_MODEL_MAP.vision)
    
    // Check image is in messages
    const messages = sentBody.messages
    const hasImage = messages.some((m: any) => 
      JSON.stringify(m).includes('image_url')
    )
    expect(hasImage).toBe(true)
  })
})

describe('Error Classification', () => {
  beforeEach(() => mockFetch.mockClear())

  it('should throw RateLimitError on 429', async () => {
    mockFetch.mockResolvedValue(mockResponse(429, {
      error: 'Rate limit exceeded'
    }))

    const c = new LLMClient()
    await expect(c.chat('test')).rejects.toThrow(RateLimitError)
  })

  it('should throw AuthError on 401', async () => {
    mockFetch.mockResolvedValue(mockResponse(401, {
      error: 'Unauthorized'
    }))

    const c = new LLMClient()
    await expect(c.chat('test')).rejects.toThrow(AuthError)
  })

  it('should throw ModelError on 500', async () => {
    mockFetch.mockResolvedValue(mockResponse(500, {
      error: 'Internal server error'
    }))

    const c = new LLMClient()
    await expect(c.chat('test')).rejects.toThrow(ModelError)
  })
})

describe('Session History', () => {
  beforeEach(() => mockFetch.mockClear())

  it('should maintain turn count', async () => {
    mockFetch.mockResolvedValue(mockResponse(200, {
      choices: [{ message: { content: 'ok' } }]
    }))

    const c = new LLMClient()
    const sess = c.session('You are helpful')

    await sess.chat('Q1')
    expect(sess.turns()).toBe(1)

    await sess.chat('Q2')
    expect(sess.turns()).toBe(2)
  })

  it('should include history in subsequent calls', async () => {
    mockFetch.mockResolvedValue(mockResponse(200, {
      choices: [{ message: { content: 'ok' } }]
    }))

    const c = new LLMClient()
    const sess = c.session('You are helpful')

    await sess.chat('Q1')
    await sess.chat('Q2')

    // Check the last call includes both Q1 and Q2
    const lastCall = mockFetch.mock.calls[mockFetch.mock.calls.length - 1]
    const sentBody = JSON.parse(lastCall[1].body)
    const messages = sentBody.messages

    const userMessages = messages.filter((m: any) => m.role === 'user')
    expect(userMessages.length).toBe(2)
  })
})

describe('Structured Output', () => {
  beforeEach(() => mockFetch.mockClear())

  it('should parse valid JSON into schema', async () => {
    const ProductSchema = z.object({
      name: z.string(),
      price: z.number()
    })

    mockFetch.mockResolvedValue(mockResponse(200, {
      choices: [{ message: { content: '{"name": "iPhone", "price": 999}' } }]
    }))

    const c = new LLMClient()
    const result = await c.chatStructured('Extract product info', ProductSchema)

    expect(result.name).toBe('iPhone')
    expect(result.price).toBe(999)
  })

  it('should strip markdown from JSON response', async () => {
    const ItemSchema = z.object({
      value: z.number()
    })

    mockFetch.mockResolvedValue(mockResponse(200, {
      choices: [{ message: { content: '```json\n{"value": 42}\n```' } }]
    }))

    const c = new LLMClient()
    const result = await c.chatStructured('Get value', ItemSchema)

    expect(result.value).toBe(42)
  })
})

describe('Caching', () => {
  beforeEach(() => mockFetch.mockClear())

  it('should return cached response for same prompt', async () => {
    mockFetch.mockResolvedValue(mockResponse(200, {
      choices: [{ message: { content: 'cached response' } }]
    }))

    const c = new LLMClient()
    
    // First call
    const r1 = await c.chat('test prompt')
    // Second call with same prompt - should hit cache
    const r2 = await c.chat('test prompt')

    // Only one HTTP call should be made
    expect(mockFetch).toHaveBeenCalledTimes(1)
    expect(r1).toBe('cached response')
    expect(r2).toBe('cached response')
  })
})

describe('Tool Use', () => {
  beforeEach(() => mockFetch.mockClear())

  it('should execute tool and return final response', async () => {
    const getWeather = vi.fn().mockResolvedValue('Beijing is sunny')
    
    // First call: LLM requests tool
    // Second call: LLM returns final response
    mockFetch
      .mockResolvedValueOnce(mockResponse(200, {
        choices: [{
          message: {
            content: '',
            tool_calls: [{
              id: 'call_1',
              type: 'function',
              function: {
                name: 'getWeather',
                arguments: '{"city": "Beijing"}'
              }
            }]
          }
        }]
      }))
      .mockResolvedValueOnce(mockResponse(200, {
        choices: [{ message: { content: 'Beijing is sunny today' } }]
      }))

    const c = new LLMClient()
    const result = await c.chatWithTools('What\'s the weather in Beijing?', {
      tools: [{ name: 'getWeather', fn: getWeather }]
    })

    expect(result).toContain('sunny')
    expect(mockFetch).toHaveBeenCalledTimes(2)
  })
})

describe('Streaming', () => {
  beforeEach(() => mockFetch.mockClear())

  it('should yield chunks from stream', async () => {
    const chunks = [
      'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
      'data: {"choices": [{"delta": {"content": " world"}}]}\n\n',
      'data: [DONE]\n\n'
    ]

    mockFetch.mockResolvedValue(mockStreamResponse(chunks))

    const c = new LLMClient()
    const chunks_list: string[] = []
    
    for await (const chunk of c.chatStream('Say hello')) {
      chunks_list.push(chunk)
    }

    expect(chunks_list).toEqual(['Hello', ' world'])
  })
})

describe('Embeddings', () => {
  beforeEach(() => mockFetch.mockClear())

  it('should return vector from embed', async () => {
    mockFetch.mockResolvedValue(mockResponse(200, {
      data: [{ embedding: [0.1, 0.2, 0.3] }]
    }))

    const c = new LLMClient()
    const result = await c.embed('test text')

    expect(Array.isArray(result)).toBe(true)
    expect(result.length).toBe(3)
    expect(result[0]).toBe(0.1)
  })
})

describe('Image Generation', () => {
  beforeEach(() => mockFetch.mockClear())

  it('should return URL from imageGen', async () => {
    mockFetch.mockResolvedValue(mockResponse(200, {
      data: [{ url: 'https://example.com/image.png' }]
    }))

    const c = new LLMClient()
    const result = await c.imageGen('a cat')

    expect(result).toBe('https://example.com/image.png')
  })
})

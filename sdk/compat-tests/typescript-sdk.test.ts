import { beforeEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'

import { LLMClient, TAG_MODEL_MAP } from '../typescript/client'
import { llmTool } from '../typescript/tools'

function chatResp(content: string) {
  return { choices: [{ message: { content, tool_calls: [] }, delta: { content } }] }
}

function toolResp(content: string, toolCalls: Array<{ id: string; name: string; arguments: Record<string, any> }>) {
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

describe('TypeScript compatibility', () => {
  const mockCreate = vi.fn()
  const mockEmbedCreate = vi.fn()
  const mockImagesGenerate = vi.fn()

  beforeEach(() => {
    mockCreate.mockReset()
    mockEmbedCreate.mockReset()
    mockImagesGenerate.mockReset()
  })

  function createClient(opts: ConstructorParameters<typeof LLMClient>[0] = {}) {
    const client = new LLMClient(opts)
    ;(client as any).openai = {
      chat: { completions: { create: mockCreate } },
      embeddings: { create: mockEmbedCreate },
      images: { generate: mockImagesGenerate },
    }
    return client
  }

  it('routes default chat and vision capability', async () => {
    mockCreate.mockResolvedValue(chatResp('hello'))

    const client = createClient()
    const result = await client.chat('hi')

    expect(result.content).toBe('hello')
    expect(mockCreate.mock.calls[0][0].model).toBe(TAG_MODEL_MAP.chat)

    await client.chat('describe', { imageUrl: 'https://example.com/image.png' })
    expect(mockCreate.mock.calls[1][0].model).toBe(TAG_MODEL_MAP.vision)
  })

  it('supports model override, stream, embedding and image generation', async () => {
    mockCreate
      .mockResolvedValueOnce(chatResp('override'))
      .mockResolvedValueOnce({
        [Symbol.asyncIterator]: async function* () {
          yield { choices: [{ delta: { content: 'a' } }] }
          yield { choices: [{ delta: { content: 'b' } }] }
        },
      })
    mockEmbedCreate.mockResolvedValue({ data: [{ embedding: [0.1, 0.2] }] })
    mockImagesGenerate.mockResolvedValue({ data: [{ url: 'https://example.com/img.png' }] })

    const client = createClient()

    await client.chat('hi', { model: 'gpt-chat' })
    expect(mockCreate.mock.calls[0][0].model).toBe('gpt-chat')

    const chunks: string[] = []
    for await (const chunk of client.chatStream('story')) {
      chunks.push(chunk)
    }

    expect(chunks.join('')).toBe('ab')
    expect(await client.embed('hello')).toEqual([0.1, 0.2])
    expect(await client.imageGen('cat')).toBe('https://example.com/img.png')
  })

  it('supports structured output and cache contract', async () => {
    mockCreate
      .mockResolvedValueOnce(chatResp('```json\n{"name":"iPhone","price":7999}\n```'))
      .mockResolvedValueOnce(chatResp('cached'))

    const client = createClient({ cache: true })
    const schema = z.object({ name: z.string(), price: z.number() })
    const result = await client.chatStructured('extract', schema)

    expect(result.name).toBe('iPhone')
    expect(result.price).toBe(7999)

    const first = await client.chat('cache me')
    const second = await client.chat('cache me')
    expect(first).toEqual({ content: 'cached', cached: false })
    expect(second).toEqual({ content: 'cached', cached: true })
    expect(mockCreate).toHaveBeenCalledTimes(2)
  })

  it('keeps session history across turns', async () => {
    mockCreate
      .mockResolvedValueOnce(chatResp('reply1'))
      .mockResolvedValueOnce(chatResp('reply2'))

    const client = createClient()
    const session = client.session('你是助手')

    await session.chat('你好')
    await session.chat('继续')

    const secondCall = mockCreate.mock.calls[1][0]
    expect(secondCall.messages.length).toBeGreaterThanOrEqual(4)
  })

  it('supports tool use contract', async () => {
    mockCreate
      .mockResolvedValueOnce(
        toolResp('', [
          { id: 'call_1', name: 'get_weather', arguments: { city: '北京' } },
        ])
      )
      .mockResolvedValueOnce(chatResp('北京今天是晴天'))

    const client = createClient()
    const getWeather = llmTool({
      name: 'get_weather',
      parameters: {
        type: 'object',
        properties: { city: { type: 'string' } },
        required: ['city'],
      },
    })((city: string) => `${city} 晴`)

    const reply = await client.chatWithTools('北京天气如何？', [getWeather])

    expect(reply).toBe('北京今天是晴天')
    const secondCall = mockCreate.mock.calls[1][0]
    expect(secondCall.messages.some((message: any) =>
      message.role === 'tool' &&
      message.tool_call_id === 'call_1' &&
      message.content === '北京 晴'
    )).toBe(true)
  })

  it('does not retry auth error', async () => {
    const error: any = new Error('Unauthorized')
    error.status = 401
    mockCreate.mockRejectedValue(error)

    const client = createClient({ maxRetries: 2 })

    await expect(client.chat('auth')).rejects.toThrow()
    expect(mockCreate).toHaveBeenCalledTimes(1)
  })
})

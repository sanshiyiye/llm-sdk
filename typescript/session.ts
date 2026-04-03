/**
 * 多轮会话 Session
 * ================
 * 用法:
 *   const sess = client.session('你是代码审查助手')
 *   const r1 = await sess.chat('审查这段代码：...')
 *   const r2 = await sess.chat('给出修复方案')
 *   sess.clear()
 */

import OpenAI from 'openai'
import type { LLMClient, ChatOptions } from './client'
import type { ZodType } from './structured'
import { extractRaw } from './structured'

const MAX_HISTORY_TOKENS = 6000

function estimateTokens(text: string): number {
  return Math.max(1, Math.floor(text.length / 4))
}

export class Session {
  private llm: LLMClient
  private system?: string
  private _history: OpenAI.ChatCompletionMessageParam[] = []

  constructor(llm: LLMClient, system?: string) {
    this.llm = llm
    this.system = system
  }

  get turns(): number {
    return Math.floor(this._history.length / 2)
  }

  get history(): OpenAI.ChatCompletionMessageParam[] {
    return [...this._history]
  }

  clear(): void {
    this._history = []
  }

  private trimHistory(): void {
    while (this._history.length >= 2) {
      const total = this._history.reduce((sum, m) => {
        const content = typeof m.content === 'string' ? m.content : JSON.stringify(m.content)
        return sum + estimateTokens(content)
      }, 0)
      if (total <= MAX_HISTORY_TOKENS) break
      this._history = this._history.slice(2)
    }
  }

  private append(role: 'user' | 'assistant', content: string): void {
    this._history.push({ role, content })
    this.trimHistory()
  }

  async chat(prompt: string, opts: Omit<ChatOptions, 'system' | 'history'> = {}): Promise<string> {
    const response = await this.llm.chat(prompt, {
      ...opts,
      system: this.system,
      history: this._history,
    })
    // Handle both dict (with cache) and string (backward compatible)
    const reply = typeof response === 'string' ? response : response.content
    this.append('user', prompt)
    this.append('assistant', reply)
    return reply
  }

  async *chatStream(
    prompt: string,
    opts: Omit<ChatOptions, 'system' | 'history'> = {},
  ): AsyncGenerator<string> {
    const chunks: string[] = []
    for await (const chunk of this.llm.chatStream(prompt, {
      ...opts,
      system: this.system,
      history: this._history,
    })) {
      chunks.push(chunk)
      yield chunk
    }
    const fullReply = chunks.join('')
    this.append('user', prompt)
    this.append('assistant', fullReply)
  }

  async chatStructured<T>(
    prompt: string,
    schema: ZodType<T>,
    opts: Omit<ChatOptions, 'system' | 'history'> = {},
  ): Promise<T> {
    const [result, rawText] = await extractRaw(this.llm, prompt, schema, {
      ...opts,
      system: this.system,
      history: this._history,
    })
    this.append('user', prompt)
    this.append('assistant', rawText)
    return result
  }
}

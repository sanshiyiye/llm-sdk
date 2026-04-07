/**
 * LLM SDK - Tool Use / Function Calling
 * =====================================
 * Enable LLM to call business functions
 *
 * Usage:
 *   import { client } from './index'
 *   import { llmTool, ChatWithToolsMixin } from './tools'
 *
 *   const getWeather = llmTool({
 *     name: 'get_weather',
 *     description: 'Get weather for a city',
 *     parameters: {
 *       type: 'object',
 *       properties: {
 *         city: { type: 'string', description: 'City name' }
 *       },
 *       required: ['city']
 *     }
 *   })(async (city: string) => {
 *     return await weatherApi.fetch(city)
 *   })
 *
 *   // Direct call
 *   const reply = await client.chatWithTools('Beijing weather?', [getWeather])
 *
 *   // Or extend client
 *   class MyClient extends ChatWithToolsMixin(LLMClient) {}
 */

import { z } from 'zod'
import { zodToJsonSchema } from 'zod-to-json-schema'

// Re-export zod types for convenience
export { z }

// Tool definition interface
export interface ToolDefinition<T extends (...args: any[]) => any = any> {
  name: string
  description: string
  parameters: Record<string, any>
  execute: T
}

// Create a tool from a function with Zod schema
export function llmTool(
  options: {
    name?: string
    description?: string
    parameters?: Record<string, any>
    schema?: z.ZodType
  },
  execute?: any
): (fn: any) => any {
  return (fn: any): any => {
    const name = options.name || fn.name
    let description = options.description || ''
    let parameters = options.parameters || { type: 'object', properties: {} }

    // If Zod schema provided, convert to JSON Schema
    if (options.schema) {
      parameters = (zodToJsonSchema as any)(options.schema, { target: 'openApi3' })
    }

    // Try to get description from function
    if (!description && (fn as any).description) {
      description = (fn as any).description
    }

    const propertyNames = Object.keys((parameters as any)?.properties ?? {})
    const executor = execute || ((args: Record<string, any>) => {
      if (propertyNames.length === 0) {
        return fn(args)
      }
      if (propertyNames.length === 1 && fn.length <= 1) {
        return fn(args[propertyNames[0]])
      }
      return fn(...propertyNames.map(key => args[key]))
    })

    return {
      name,
      description,
      parameters,
      execute: executor,
    }
  }
}

// Decorator style (for class methods)
export function tool(
  name?: string,
  description?: string,
  parameters?: Record<string, any>,
) {
  return function (target: any, propertyKey: string, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value
    descriptor.value = function (...args: any[]) {
      return originalMethod.apply(this, args)
    }
    // Store tool metadata
    ;(descriptor.value as any).toolMeta = {
      name: name || propertyKey,
      description: description || '',
      parameters: parameters || { type: 'object', properties: {} },
    }
    return descriptor
  }
}

// Tool call result
export class ToolCall {
  constructor(
    public toolCallId: string,
    public name: string,
    public args: Record<string, any>,
  ) {}

  async execute(tools: Map<string, ToolDefinition>): Promise<string> {
    const tool = tools.get(this.name)
    if (!tool) {
      return `Error: Unknown tool '${this.name}'`
    }

    try {
      const result = await tool.execute(this.args)
      if (typeof result === 'object' && result !== null) {
        return JSON.stringify(result)
      }
      return String(result)
    } catch (e) {
      return `Error: ${e instanceof Error ? e.message : String(e)}`
    }
  }

  toMessage() {
    return {
      id: this.toolCallId,
      type: 'function',
      function: {
        name: this.name,
        arguments: JSON.stringify(this.args),
      },
    }
  }
}

function extractToolCalls(content: string, rawToolCalls?: any[]): ToolCall[] {
  if (rawToolCalls?.length) {
    return rawToolCalls.map(
      (toolCall: any) =>
        new ToolCall(
          toolCall.id,
          toolCall.function.name,
          JSON.parse(toolCall.function.arguments || '{}'),
        ),
    )
  }

  try {
    const match = content.match(/\[[\s\S]*\]/)
    if (!match) {
      return []
    }
    const parsed = JSON.parse(match[0])
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed
      .filter((c: any) => c && c.name)
      .map(
        (c: any, i: number) =>
          new ToolCall(
            String(i),
            c.name,
            c.arguments || {},
          ),
      )
  } catch {
    return []
  }
}

export async function chatWithTools(
  client: any,
  prompt: string,
  tools: ToolDefinition[],
  opts: {
    system?: string
    history?: any[]
    capability?: string
    model?: string
    maxToolCalls?: number
    imageUrl?: string
    imageBase64?: { data: string; mime?: string }
    maxTokens?: number
    temperature?: number
    [key: string]: any
  } = {},
): Promise<string> {
  const maxToolCalls = opts.maxToolCalls || 10
  const toolMap = new Map<string, ToolDefinition>()
  for (const tool of tools) {
    toolMap.set(tool.name, tool)
  }

  const { maxToolCalls: _maxToolCalls, ...requestOpts } = opts
  const hasImage = !!(requestOpts.imageUrl || requestOpts.imageBase64)
  const model = client.resolveModel('chat', hasImage, requestOpts)
  const messages = client.buildMessages(prompt, requestOpts)

  for (let i = 0; i < maxToolCalls; i++) {
    const response = await client.openai.chat.completions.create({
      model,
      messages,
      tools: tools.map(t => toolToOpenAISchema(t)),
      tool_choice: 'auto',
      ...(requestOpts.maxTokens ? { max_tokens: requestOpts.maxTokens } : {}),
      ...(requestOpts.temperature !== undefined ? { temperature: requestOpts.temperature } : {}),
    })

    const message = response.choices[0]?.message
    const content = message?.content || ''
    const toolCalls = extractToolCalls(content, message?.tool_calls as any[])
    const assistantMessage: any = { role: 'assistant', content }
    if (toolCalls.length) {
      assistantMessage.tool_calls = toolCalls.map(tc => tc.toMessage())
    }
    messages.push(assistantMessage)

    if (!toolCalls.length) {
      return content
    }

    for (const tc of toolCalls) {
      const result = await tc.execute(toolMap)
      messages.push({
        role: 'tool',
        tool_call_id: tc.toolCallId,
        content: result,
      })
    }
  }

  return 'Tool call limit reached'
}

export function ChatWithToolsMixin<T extends new (...args: any[]) => any>(Client: T) {
  return class extends Client {
    async chatWithTools(
      prompt: string,
      tools: ToolDefinition[],
      opts: {
        system?: string
        history?: any[]
        capability?: string
        model?: string
        maxToolCalls?: number
        [key: string]: any
      } = {},
    ): Promise<string> {
      return chatWithTools(this, prompt, tools, opts)
    }
  } as any
}

// Helper to convert to OpenAI schema format
export function toolToOpenAISchema(tool: ToolDefinition): any {
  return {
    type: 'function',
    function: {
      name: tool.name,
      description: tool.description,
      parameters: tool.parameters,
    },
  }
}

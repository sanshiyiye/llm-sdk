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

    return {
      name,
      description,
      parameters,
      execute: execute || fn,
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

  execute(tools: Map<string, ToolDefinition>): string {
    const tool = tools.get(this.name)
    if (!tool) {
      return `Error: Unknown tool '${this.name}'`
    }

    try {
      const result = tool.execute(this.args)
      // Handle promises
      if (result instanceof Promise) {
        // Note: In async context, caller should await
        return 'Error: Async function must be awaited'
      }
      return String(result)
    } catch (e) {
      return `Error: ${e instanceof Error ? e.message : String(e)}`
    }
  }
}

// Mixin for adding chatWithTools to client
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
      const maxToolCalls = opts.maxToolCalls || 10

      // Build tool map
      const toolMap = new Map<string, ToolDefinition>()
      for (const tool of tools) {
        toolMap.set(tool.name, tool)
      }

      // Build messages
      const messages: any[] = []
      if (opts.system) messages.push({ role: 'system', content: opts.system })
      if (opts.history) messages.push(...opts.history)
      messages.push({ role: 'user', content: prompt })

      // Tool call loop
      for (let i = 0; i < maxToolCalls; i++) {
        // Call LLM with tools
        const response = await (this as any).chat(prompt, {
          ...opts,
          tools: tools.map(t => toolToOpenAISchema(t)),
        })

        // Get content (handle both string and object with cached flag)
        const content = typeof response === 'string' ? response : response.content
        messages.push({ role: 'assistant', content })

        // Extract tool calls
        const toolCalls = this.extractToolCalls(content)
        if (!toolCalls.length) {
          return content
        }

        // Execute tools
        for (const tc of toolCalls) {
          const result = tc.execute(toolMap)
          messages.push({
            role: 'tool',
            tool_call_id: tc.toolCallId,
            content: result,
          })
        }
      }

      return 'Tool call limit reached'
    }

    private extractToolCalls(content: string): ToolCall[] {
      // Try to parse JSON array format
      try {
        const match = content.match(/\[[\s\S]*\]/)
        if (match) {
          const parsed = JSON.parse(match[0])
          if (Array.isArray(parsed)) {
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
          }
        }
      } catch {
        // Ignore parse errors
      }
      return []
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

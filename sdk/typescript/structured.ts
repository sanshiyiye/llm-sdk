/**
 * 结构化输出 (chatStructured)
 * ===========================
 * 用法:
 *   import { z } from 'zod'
 *   import { client } from './llm_sdk'
 *
 *   const ProductSchema = z.object({
 *     name: z.string(),
 *     price: z.number(),
 *   })
 *
 *   const result = await client.chatStructured(
 *     '提取商品信息：iPhone 16 Pro 售价 7999',
 *     ProductSchema,
 *   )
 *   console.log(result.name, result.price)
 */

import { z } from 'zod'
import { zodToJsonSchema } from 'zod-to-json-schema'
import { StructuredOutputError } from './errors'
import type { LLMClient, ChatOptions } from './client'

// 导出类型供其他模块使用
export type ZodType<T> = z.ZodType<T>
export type ZodInfer<T extends z.ZodType> = z.infer<T>

const SYSTEM_TEMPLATE = `请严格按照以下 JSON Schema 返回结果。
只返回合法的 JSON 对象，不要包含 Markdown 代码块、注释或任何其他内容。

Schema:
{schema}`

function extractJson(text: string): string {
  text = text.trim()
  const mdMatch = text.match(/```(?:json)?\s*([\s\S]+?)\s*```/)
  if (mdMatch) return mdMatch[1].trim()
  const start = text.indexOf('{')
  const end = text.lastIndexOf('}')
  if (start !== -1 && end > start) return text.slice(start, end + 1)
  return text
}

/** 内部实现：返回 [解析结果, 原始文本]，供 Session 使用 */
export async function extractRaw<T>(
  llm: LLMClient,
  prompt: string,
  schema: z.ZodType<T>,
  opts: ChatOptions = {},
): Promise<[T, string]> {
  const jsonSchema = JSON.stringify(zodToJsonSchema(schema as any), null, 2)
  const structuredSystem = SYSTEM_TEMPLATE.replace('{schema}', jsonSchema)
  const combinedSystem = opts.system
    ? `${opts.system}\n\n${structuredSystem}`
    : structuredSystem

  const raw = await llm.chat(prompt, { ...opts, system: combinedSystem })
  const content = typeof raw === 'string' ? raw : raw.content
  const jsonStr = extractJson(content)

  try {
    const data = JSON.parse(jsonStr)
    const result = schema.parse(data)
    return [result, content]
  } catch (e) {
    throw new StructuredOutputError(`结构化输出解析失败: ${e}`, content)
  }
}

/** 对外接口 */
export async function chatStructured<T>(
  llm: LLMClient,
  prompt: string,
  schema: z.ZodType<T>,
  opts: ChatOptions = {},
): Promise<T> {
  const [result] = await extractRaw(llm, prompt, schema, opts)
  return result
}

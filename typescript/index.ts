export { LLMClient, TAG_MODEL_MAP, resolveModel, client } from './client'
export type { Capability, ChatOptions, EmbedOptions, ImageGenOptions, LLMClientOptions } from './client'
export { Session } from './session'
export { chatStructured, extractRaw } from './structured'
export type { ZodType, ZodInfer } from './structured'
export { TemplateRegistry, templates } from './templates'
export { createCache, buildCacheKey } from './cache'
export type { CacheBackend, CacheOptions, TTLCacheOptions, RedisCacheOptions } from './cache'
export { llmTool, tool, ToolCall, ChatWithToolsMixin, toolToOpenAISchema } from './tools'
export { z } from 'zod'
export type { ToolDefinition } from './tools'
export {
  LLMError, RateLimitError, TimeoutError, ModelError,
  ProxyError, AuthError, NetworkError,
  StructuredOutputError, TemplateNotFoundError,
} from './errors'

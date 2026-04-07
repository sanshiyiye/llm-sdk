/**
 * LLM SDK 错误体系
 * 所有错误继承自 LLMError
 */

export class LLMError extends Error {
  readonly statusCode: number
  readonly raw: string
  constructor(message: string, statusCode = 0, raw = '') {
    super(message)
    this.name = this.constructor.name
    this.statusCode = statusCode
    this.raw = raw
  }
}

export class RateLimitError extends LLMError {
  readonly retryAfter: number
  constructor(message = 'Rate limit exceeded', retryAfter = 5, raw = '') {
    super(message, 429, raw)
    this.retryAfter = retryAfter
  }
}

export class TimeoutError extends LLMError {
  constructor(message = 'Request timed out', raw = '') {
    super(message, 408, raw)
  }
}

export class ModelError extends LLMError {
  constructor(message: string, statusCode: number, raw = '') {
    super(message, statusCode, raw)
  }
}

export class ProxyError extends LLMError {
  constructor(message: string, statusCode: number, raw = '') {
    super(message, statusCode, raw)
  }
}

export class AuthError extends LLMError {
  constructor(message = 'Authentication failed', raw = '') {
    super(message, 401, raw)
  }
}

export class NetworkError extends LLMError {
  constructor(message: string) {
    super(message, 0)
  }
}

export class StructuredOutputError extends LLMError {
  readonly rawResponse: string
  constructor(message: string, rawResponse = '') {
    super(message)
    this.rawResponse = rawResponse
  }
}

export class TemplateNotFoundError extends LLMError {
  readonly templateName: string
  constructor(name: string) {
    super(`模板未找到: '${name}'`)
    this.templateName = name
  }
}

/** 根据 HTTP status 分类错误 */
export function classifyError(status: number, raw: string): LLMError {
  if (status === 401 || status === 403) return new AuthError(undefined, raw)
  if (status === 429) return new RateLimitError(undefined, 5, raw)
  if (status === 400 || status === 422) return new ModelError(`模型拒绝请求 (HTTP ${status})`, status, raw)
  if ([500, 502, 503, 504].includes(status)) return new ProxyError(`Proxy 错误 (HTTP ${status})`, status, raw)
  return new LLMError(`HTTP ${status}`, status, raw)
}

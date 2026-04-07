/**
 * LLM SDK - Cache Module
 * ======================
 * Memory TTLCache and optional Redis backend support
 *
 * Usage:
 *   import { LLMClient } from './client'
 *
 *   // Memory cache (default)
 *   const c = new LLMClient({ cache: true })
 *
 *   // Redis cache
 *   const c = new LLMClient({ cache: { type: 'redis', url: 'redis://localhost:6379' }})
 */

import crypto from 'crypto'

export interface CacheBackend {
  get(key: string): unknown | undefined
  set(key: string, value: unknown, ttl?: number): void
}

export interface TTLCacheOptions {
  type?: 'memory'
  maxSize?: number
  ttl?: number
}

export interface RedisCacheOptions {
  type: 'redis'
  url: string
  ttl?: number
}

export type CacheOptions = boolean | TTLCacheOptions | RedisCacheOptions

// In-memory TTLCache implementation
class TTLCacheImpl implements CacheBackend {
  private cache = new Map<string, { value: unknown; expiresAt: number }>()
  private maxSize: number
  private ttl: number

  constructor(maxSize = 1000, ttl = 3600) {
    this.maxSize = maxSize
    this.ttl = ttl
  }

  get(key: string): unknown | undefined {
    const entry = this.cache.get(key)
    if (!entry) return undefined
    if (Date.now() > entry.expiresAt) {
      this.cache.delete(key)
      return undefined
    }
    return entry.value
  }

  set(key: string, value: unknown, ttl?: number): void {
    // Evict oldest if at capacity
    if (this.cache.size >= this.maxSize && !this.cache.has(key)) {
      const firstKey = this.cache.keys().next().value
      if (firstKey) this.cache.delete(firstKey)
    }
    const effectiveTtl = ttl ?? this.ttl
    this.cache.set(key, { value, expiresAt: Date.now() + effectiveTtl * 1000 })
  }
}

// Optional Redis cache (requires ioredis package)
let Redis: any = null
try {
  Redis = require('ioredis')
} catch {
  // Redis not available
}

class RedisCacheImpl implements CacheBackend {
  private client: any
  private ttl: number

  constructor(url: string, ttl = 3600) {
    if (!Redis) throw new Error('ioredis not installed: npm install ioredis')
    this.client = new Redis(url)
    this.ttl = ttl
  }

  get(key: string): unknown | undefined {
    // Synchronous-like get using sync methods
    const value = this.client.get(key)
    if (!value) return undefined
    try {
      return JSON.parse(value)
    } catch {
      return value
    }
  }

  set(key: string, value: unknown, ttl?: number): void {
    const serialized = JSON.stringify(value)
    this.client.setex(key, ttl ?? this.ttl, serialized)
  }
}

export function buildCacheKey(model: string, messages: unknown[]): string {
  const content = JSON.stringify({ model, messages })
  return crypto.createHash('sha256').update(content).digest('hex')
}

export function createCache(config: CacheOptions): CacheBackend | null {
  if (!config) return null
  
  // Handle boolean case
  if (typeof config === 'boolean') {
    return config ? new TTLCacheImpl() : null
  }

  if (config.type === 'redis') {
    return new RedisCacheImpl(config.url, config.ttl)
  }
  // Default to memory
  return new TTLCacheImpl(config.maxSize, config.ttl)

  return new TTLCacheImpl()
}

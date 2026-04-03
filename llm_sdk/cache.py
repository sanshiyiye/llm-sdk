"""
LLM SDK - 缓存模块
==================
支持内存 TTLCache 和可选 Redis 后端

用法:
    from llm_sdk import client

    # 内存缓存（默认）
    c = client.LLMClient(cache=True)

    # Redis 缓存
    c = client.LLMClient(cache={"type": "redis", "url": "redis://localhost:6379"})
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

# 可选依赖
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class CacheBackend:
    """缓存后端基类"""

    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl: int) -> None: ...


class TTLCache(CacheBackend):
    """内存 TTLCache 实现"""

    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        if key not in self._cache:
            return None
        value, expire_at = self._cache[key]
        if time.time() > expire_at:
            del self._cache[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        if ttl is None:
            ttl = self._ttl
        # 淘汰最老的条目
        if len(self._cache) >= self._maxsize:
            oldest = min(self._cache.items(), key=lambda x: x[1][1])
            del oldest[0]
        self._cache[key] = (value, time.time() + ttl)


class RedisCache(CacheBackend):
    """Redis 缓存后端（需要 pip install redis）"""

    def __init__(self, url: str = "redis://localhost:6379", ttl: int = 3600):
        if not REDIS_AVAILABLE:
            raise ImportError("redis 库未安装: pip install redis")
        self._client = redis.from_url(url)
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        value = self._client.get(key)
        if value is None:
            return None
        return json.loads(value)

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        if ttl is None:
            ttl = self._ttl
        self._client.setex(key, ttl, json.dumps(value))


def build_cache_key(model: str, messages: list[dict]) -> str:
    """构建缓存 key: hash(model + messages_json)"""
    content = json.dumps({"model": model, "messages": messages}, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def create_cache(config: dict | bool | None) -> CacheBackend | None:
    """
    根据配置创建缓存后端

    Args:
        config:
            - True/None: 创建默认 TTLCache
            - dict: {"type": "redis", "url": "...", "ttl": 3600}
            - TTLCache 实例: 直接返回
            - False: 不使用缓存

    Returns:
        CacheBackend 实例或 None
    """
    if config is None or config is True:
        return TTLCache()
    if config is False:
        return None
    if isinstance(config, dict):
        cache_type = config.get("type", "memory")
        if cache_type == "redis":
            return RedisCache(
                url=config.get("url", "redis://localhost:6379"),
                ttl=config.get("ttl", 3600),
            )
        elif cache_type == "memory":
            return TTLCache(
                maxsize=config.get("maxsize", 1000),
                ttl=config.get("ttl", 3600),
            )
    if isinstance(config, CacheBackend):
        return config
    return None

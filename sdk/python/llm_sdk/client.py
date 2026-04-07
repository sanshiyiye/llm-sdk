"""
LLM SDK - Python
================
用法:
    from llm_sdk import client
    reply  = client.chat("你好")
    reply  = client.chat("描述图片", image_url="https://...")
    reply  = client.chat("快速回答", capability="fast")
    vec    = client.embed("some text")
    imgurl = client.image_gen("a cat on the moon")
    stream = client.chat_stream("写一篇文章")
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import AsyncIterator, Iterator

import httpx
import openai

from .cache import build_cache_key, create_cache
from .errors import (
    AuthError,
    LLMError,
    ModelError,
    NetworkError,
    ProxyError,
    RateLimitError,
    TimeoutError,
)

# ── Capability tag → model_name 映射 ────────────────────────────────────────

TAG_MODEL_MAP: dict[str, str] = {
    "chat": os.getenv("LLM_MODEL_CHAT", "auto-chat"),
    "vision": os.getenv("LLM_MODEL_VISION", "auto-vision"),
    "video-input": os.getenv("LLM_MODEL_VIDEO", "gemini-vision"),
    "embedding": os.getenv("LLM_MODEL_EMBEDDING", "text-embedding"),
    "image-gen": os.getenv("LLM_MODEL_IMAGE_GEN", "gpt-image-gen"),
    "fast": os.getenv("LLM_MODEL_FAST", "gemini-chat"),
    "local": os.getenv("LLM_MODEL_LOCAL", "local-chat"),
}

_RETRY_STATUSES = {500, 502, 503, 504}
_NO_RETRY_STATUSES = {400, 401, 403, 422}


def _resolve_model(capability: str) -> str:
    model = TAG_MODEL_MAP.get(capability)
    if not model:
        raise ValueError(
            f"未知 capability: '{capability}'，可用值: {list(TAG_MODEL_MAP.keys())}"
        )
    return model


def _classify_error(status: int, body: str) -> LLMError:
    if status == 401 or status == 403:
        return AuthError(raw=body)
    if status == 429:
        return RateLimitError(raw=body)
    if status in (400, 422):
        return ModelError(f"模型拒绝请求 (HTTP {status})", status_code=status, raw=body)
    if status in _RETRY_STATUSES:
        return ProxyError(f"Proxy 错误 (HTTP {status})", status_code=status, raw=body)
    return LLMError(f"HTTP {status}", status_code=status, raw=body)


def _with_retry(fn, max_retries: int = 2, base_delay: float = 1.0):
    """通用重试包装，指数退避，不可恢复错误立即抛出"""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except (AuthError, ModelError):
            raise  # 不重试
        except RateLimitError as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(e.retry_after)
        except (TimeoutError, ProxyError, NetworkError) as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(base_delay * (2**attempt))
        except Exception as e:
            raise NetworkError(str(e)) from e
    raise last_err


# ── 主客户端 ─────────────────────────────────────────────────────────────────


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        max_retries: int = 2,
        timeout: float = 60.0,
        cache: dict | bool | None = None,
    ):
        self._base_url = base_url or os.getenv("LLM_BASE_URL", "http://localhost:4000")
        self._api_key = api_key or os.getenv("LLM_API_KEY", "no-key")
        self._max_retries = max_retries
        self._timeout = timeout
        self._cache = create_cache(cache)
        self._openai = openai.OpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
            max_retries=0,  # 重试由 SDK 层统一控制
            timeout=timeout,
        )

    # ── 内部工具 ─────────────────────────────────────────────────────────────

    def _build_messages(
        self,
        prompt: str,
        system: str | None,
        history: list[dict] | None,
        image_url: str | None,
        image_path: str | None,
    ) -> list[dict]:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            messages.extend(history)

        has_image = bool(image_url or image_path)
        if has_image:
            content: list[dict] = [{"type": "text", "text": prompt}]
            if image_url:
                content.append({"type": "image_url", "image_url": {"url": image_url}})
            if image_path:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": _file_to_data_url(image_path)},
                    }
                )
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})
        return messages

    def _resolve(
        self, capability: str | None, model: str | None, has_image: bool
    ) -> str:
        if model:
            return model
        cap = capability or ("vision" if has_image else "chat")
        return _resolve_model(cap)

    def _call_chat(self, model: str, messages: list[dict], **kwargs) -> str:
        def _do():
            try:
                resp = self._openai.chat.completions.create(
                    model=model, messages=messages, **kwargs
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                raw = str(e)
                code = getattr(e, "status_code", 0)
                raise _classify_error(code, raw) from e

        return _with_retry(_do, self._max_retries)

    # ── 公开接口 ─────────────────────────────────────────────────────────────

    def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        history: list[dict] | None = None,
        image_url: str | None = None,
        image_path: str | None = None,
        capability: str | None = None,
        model: str | None = None,
        cache: bool = True,
        **kwargs,
    ) -> dict:
        """发送一次对话，返回模型回复文本

        Returns:
            dict: {"content": str, "_cached": bool}
        """
        has_image = bool(image_url or image_path)
        resolved = self._resolve(capability, model, has_image)
        messages = self._build_messages(prompt, system, history, image_url, image_path)

        # Check cache if enabled
        if cache and self._cache:
            cache_key = build_cache_key(resolved, messages)
            cached_value = self._cache.get(cache_key)
            if cached_value is not None:
                return {"content": cached_value, "_cached": True}

        # Make API call
        result = self._call_chat(resolved, messages, **kwargs)

        # Store in cache if enabled
        if cache and self._cache:
            cache_key = build_cache_key(resolved, messages)
            self._cache.set(cache_key, result)  # type: ignore

        return {"content": result, "_cached": False}

    def chat_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        history: list[dict] | None = None,
        image_url: str | None = None,
        capability: str | None = None,
        model: str | None = None,
        **kwargs,
    ) -> Iterator[str]:
        """流式对话，yield 每个文本块"""
        has_image = bool(image_url)
        resolved = self._resolve(capability, model, has_image)
        messages = self._build_messages(prompt, system, history, image_url, None)
        try:
            with self._openai.chat.completions.stream(
                model=resolved, messages=messages, **kwargs
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            code = getattr(e, "status_code", 0)
            raise _classify_error(code, str(e)) from e

    def embed(
        self,
        text: str | list[str],
        *,
        model: str | None = None,
    ) -> list[float] | list[list[float]]:
        """文本向量化"""
        resolved = model or _resolve_model("embedding")

        def _do():
            try:
                resp = self._openai.embeddings.create(model=resolved, input=text)
                if isinstance(text, str):
                    return resp.data[0].embedding
                return [d.embedding for d in resp.data]
            except Exception as e:
                raise _classify_error(getattr(e, "status_code", 0), str(e)) from e

        return _with_retry(_do, self._max_retries)

    def image_gen(
        self,
        prompt: str,
        *,
        size: str = "1024x1024",
        model: str | None = None,
        **kwargs,
    ) -> str:
        """图像生成，返回 URL"""
        resolved = model or _resolve_model("image-gen")

        def _do():
            try:
                resp = self._openai.images.generate(
                    model=resolved, prompt=prompt, size=size, **kwargs
                )
                return resp.data[0].url or ""
            except Exception as e:
                raise _classify_error(getattr(e, "status_code", 0), str(e)) from e

        return _with_retry(_do, self._max_retries)

    def session(self, system: str | None = None) -> "Session":
        """创建多轮会话对象"""
        from .session import Session

        return Session(self, system=system)


# ── 工具函数 ─────────────────────────────────────────────────────────────────


def _file_to_data_url(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lstrip(".").lower()
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, "image/png")
    data = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


# ── 单例 ─────────────────────────────────────────────────────────────────────
client = LLMClient()

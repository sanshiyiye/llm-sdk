"""
多轮会话 Session
===============
用法:
    session = client.session(system="你是代码审查助手")
    r1 = session.chat("审查这段代码：...")
    r2 = session.chat("给第一个问题一个修复方案")
    session.clear()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, Type, TypeVar

if TYPE_CHECKING:
    from .client import LLMClient

T = TypeVar("T")

# history 超过此 token 估算值时，截断最早的非 system 轮
_MAX_HISTORY_TOKENS = 6000


def _estimate_tokens(text: str) -> int:
    """粗估 token 数（1 token ≈ 4 字符）"""
    return max(1, len(text) // 4)


class Session:
    """
    封装多轮对话 history，业务代码只需调用 chat()，
    无需手动维护 messages 列表。
    """

    def __init__(self, llm: "LLMClient", system: str | None = None):
        self._llm = llm
        self._system = system
        self._history: list[dict] = []  # 不含 system，只含 user/assistant

    # ── 状态查询 ─────────────────────────────────────────────────────────────

    @property
    def turns(self) -> int:
        """已完成的对话轮数（1 user + 1 assistant = 1 轮）"""
        return len(self._history) // 2

    @property
    def history(self) -> list[dict]:
        """只读 history 快照"""
        return list(self._history)

    def clear(self) -> None:
        """清空 history，保留 system prompt"""
        self._history = []

    # ── 内部工具 ─────────────────────────────────────────────────────────────

    def _trim_history(self) -> None:
        """当 history 过长时，移除最早的完整轮（user+assistant 对）"""
        while len(self._history) >= 2:
            total = sum(
                _estimate_tokens(
                    m["content"] if isinstance(m["content"], str) else str(m["content"])
                )
                for m in self._history
            )
            if total <= _MAX_HISTORY_TOKENS:
                break
            # 移除最早一轮（user + assistant）
            self._history = self._history[2:]

    def _append(self, role: str, content: str) -> None:
        self._history.append({"role": role, "content": content})
        self._trim_history()

    # ── 公开接口 ─────────────────────────────────────────────────────────────

    def chat(
        self,
        prompt: str,
        *,
        image_url: str | None = None,
        image_path: str | None = None,
        capability: str | None = None,
        model: str | None = None,
        cache: bool = True,
        **kwargs,
    ) -> str:
        """发送一轮对话，自动携带历史"""
        response = self._llm.chat(
            prompt,
            system=self._system,
            history=self._history,
            image_url=image_url,
            image_path=image_path,
            capability=capability,
            model=model,
            cache=cache,
            **kwargs,
        )
        # Handle both dict (with cache) and string (backward compatible)
        if isinstance(response, dict):
            reply = response.get("content", "")
        else:
            reply = response
        self._append("user", prompt)
        self._append("assistant", reply)
        return reply

    def chat_stream(
        self,
        prompt: str,
        *,
        capability: str | None = None,
        model: str | None = None,
        **kwargs,
    ) -> Iterator[str]:
        """流式对话，流结束后自动追加到 history"""
        chunks: list[str] = []
        for chunk in self._llm.chat_stream(
            prompt,
            system=self._system,
            history=self._history,
            capability=capability,
            model=model,
            **kwargs,
        ):
            chunks.append(chunk)
            yield chunk
        full_reply = "".join(chunks)
        self._append("user", prompt)
        self._append("assistant", full_reply)

    def chat_structured(
        self,
        prompt: str,
        schema: Type[T],
        *,
        capability: str | None = None,
        model: str | None = None,
        **kwargs,
    ) -> T:
        """结构化输出 + 自动维护 history"""
        from .structured import chat_structured as _cs

        result, reply_text = _cs(
            self._llm,
            prompt,
            schema,
            system=self._system,
            history=self._history,
            capability=capability,
            model=model,
            _return_raw=True,
            **kwargs,
        )
        self._append("user", prompt)
        self._append("assistant", reply_text)
        return result

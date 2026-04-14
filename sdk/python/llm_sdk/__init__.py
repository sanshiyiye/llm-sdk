"""
LLM SDK - Python
================
快速使用:
    from llm_sdk import client, templates
    from llm_sdk.errors import LLMError

    reply  = client.chat("你好")
    vec    = client.embed("some text")
    img    = client.image_gen("a cat")
    sess   = client.session(system="你是助手")

    # 结构化输出（需要 pydantic）
    from pydantic import BaseModel
    class Answer(BaseModel):
        text: str
        confidence: float
    result = client.chat_structured("回答这个问题", schema=Answer)

    # Prompt 模板
    templates.register("greet", user="用 {lang} 打招呼")
    reply = templates.chat_with_template(client, "greet", lang="日语")
"""

from .cache import TTLCache, RedisCache, create_cache, build_cache_key
from .client import LLMClient, TAG_MODEL_MAP, client
from .doctor import DoctorResult, DoctorCheck
from .errors import (
    AuthError,
    LLMError,
    ModelError,
    NetworkError,
    ProxyError,
    RateLimitError,
    StructuredOutputError,
    TemplateNotFoundError,
    TimeoutError,
)
from .session import Session
from .structured import chat_structured
from .templates import TemplateRegistry, templates
from .tools import llm_tool, ToolDefinition, ToolCall, ChatWithToolsMixin, chat_with_tools


# chat_structured 注入到 LLMClient（避免循环导入）
def _client_chat_structured(self, prompt, schema, **kwargs):
    return chat_structured(self, prompt, schema, **kwargs)


LLMClient.chat_structured = _client_chat_structured


# chat_with_template 注入
def _client_chat_with_template(self, template_name, **kwargs):
    return templates.chat_with_template(self, template_name, **kwargs)


LLMClient.chat_with_template = _client_chat_with_template


def _client_chat_with_tools(self, prompt, tools, **kwargs):
    return chat_with_tools(self, prompt, tools, **kwargs)


LLMClient.chat_with_tools = _client_chat_with_tools

__all__ = [
    "LLMClient",
    "TAG_MODEL_MAP",
    "client",
    "Session",
    "chat_structured",
    "TemplateRegistry",
    "templates",
    # Doctor
    "DoctorResult",
    "DoctorCheck",
    # Errors
    "LLMError",
    "RateLimitError",
    "TimeoutError",
    "ModelError",
    "ProxyError",
    "AuthError",
    "NetworkError",
    "StructuredOutputError",
    "TemplateNotFoundError",
    # Cache
    "TTLCache",
    "RedisCache",
    "create_cache",
    "build_cache_key",
    # Tools
    "llm_tool",
    "ToolDefinition",
    "ToolCall",
    "ChatWithToolsMixin",
    "chat_with_tools",
]

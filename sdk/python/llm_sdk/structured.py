"""
结构化输出 (chat_structured)
============================
用法:
    from pydantic import BaseModel
    from llm_sdk import client

    class Product(BaseModel):
        name: str
        price: float
        category: str

    result = client.chat_structured(
        "提取商品信息：iPhone 16 Pro 售价 7999，手机类",
        schema=Product,
    )
    print(result.name, result.price)
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Type, TypeVar

from .errors import StructuredOutputError

if TYPE_CHECKING:
    from .client import LLMClient

T = TypeVar("T")

_SYSTEM_TEMPLATE = """\
请严格按照以下 JSON Schema 返回结果。
只返回合法的 JSON 对象，不要包含 Markdown 代码块、注释或任何其他内容。

Schema:
{schema}"""


def _model_to_schema(schema_cls: Type) -> str:
    """将 Pydantic BaseModel 转为 JSON Schema 字符串"""
    try:
        return json.dumps(schema_cls.model_json_schema(), ensure_ascii=False, indent=2)
    except AttributeError:
        # Pydantic v1 兼容
        try:
            return json.dumps(schema_cls.schema(), ensure_ascii=False, indent=2)
        except Exception as e:
            raise TypeError(f"schema 必须是 Pydantic BaseModel 子类: {e}") from e


def _extract_json(text: str) -> str:
    """从模型回复中提取 JSON，兼容带 markdown 代码块的情况"""
    # 去掉 ```json ... ``` 包裹
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return match.group(1).strip()
    # 尝试找第一个 { ... } 块
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def chat_structured(
    llm: "LLMClient",
    prompt: str,
    schema: Type[T],
    *,
    system: str | None = None,
    history: list[dict] | None = None,
    capability: str | None = None,
    model: str | None = None,
    _return_raw: bool = False,
    **kwargs,
) -> T:
    """
    内部实现。对外通过 LLMClient.chat_structured() 调用。
    _return_raw=True 时返回 (result, raw_text)，供 Session 使用。
    """
    schema_str = _model_to_schema(schema)
    structured_system = _SYSTEM_TEMPLATE.format(schema=schema_str)

    # 如果业务层传了 system，追加在结构化指令之后
    combined_system = structured_system
    if system:
        combined_system = f"{system}\n\n{structured_system}"

    raw = llm.chat(
        prompt,
        system=combined_system,
        history=history,
        capability=capability,
        model=model,
        **kwargs,
    )

    content = raw if isinstance(raw, str) else raw.get("content", "")
    json_str = _extract_json(content)
    try:
        data = json.loads(json_str)
        result = schema.model_validate(data)
    except Exception:
        # Pydantic v1 兼容
        try:
            data = json.loads(json_str)
            result = schema(**data)
        except Exception as e:
            raise StructuredOutputError(
                f"结构化输出解析失败: {e}",
                raw_response=raw,
            ) from e

    if _return_raw:
        return result, raw
    return result

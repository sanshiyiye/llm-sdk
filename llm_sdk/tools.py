"""
LLM SDK - Tool Use / Function Calling
====================================
让 LLM 能调用业务函数

用法:
    from llm_sdk import client
    from llm_sdk.tools import llm_tool, ChatWithToolsMixin

    @llm_tool
    def get_weather(city: str) -> str:
        '''获取城市天气

        Args:
            city: 城市名称，如 "北京"
        '''
        return weather_api.fetch(city)

    # 方式1: 直接调用
    reply = client.chat_with_tools("北京今天天气如何？", tools=[get_weather])

    # 方式2: 继承 mixin
    class MyClient(ChatWithToolsMixin, LLMClient):
        pass

    c = MyClient()
    reply = c.chat_with_tools("北京天气？", tools=[get_weather])
"""

from __future__ import annotations

import inspect
import json
from typing import Any, Callable, TypeVar, get_type_hints

T = TypeVar("T")


class ToolDefinition:
    """工具定义"""

    def __init__(
        self, func: Callable, name: str | None = None, description: str | None = None
    ):
        self.func = func
        self.name = name or func.__name__
        self.description = description or func.__doc__ or ""
        self.parameters = self._build_parameters(func)

    def _build_parameters(self, func: Callable) -> dict:
        """从函数签名构建 JSON Schema"""
        sig = inspect.signature(func)
        hints = {}
        try:
            hints = get_type_hints(func)
        except Exception:
            pass  # 忽略类型提示解析错误

        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            # 获取类型
            param_type = hints.get(param_name, str)
            json_type = self._python_type_to_json(param_type)

            # 获取描述（从 docstring 解析）
            description = ""
            if self.description:
                # 简单解析：查找 Args: 段落
                lines = self.description.split("\n")
                in_args = False
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("Args:"):
                        in_args = True
                        continue
                    if in_args and param_name in stripped:
                        # 找到参数描述
                        desc_part = stripped.split(":", 1)
                        if len(desc_part) > 1:
                            description = desc_part[1].strip()
                        break

            properties[param_name] = {
                "type": json_type,
            }
            if description:
                properties[param_name]["description"] = description

            # 检查是否有默认值
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "object",
            "properties": properties,
        }
        if required:
            schema["required"] = required

        return schema

    def _python_type_to_json(self, py_type: Any) -> str:
        """Python 类型转 JSON Schema 类型"""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        # 处理 Optional[X]
        origin = getattr(py_type, "__origin__", None)
        if origin is list:
            return "array"
        if origin is dict:
            return "object"
        # 处理 Optional
        if hasattr(py_type, "__args__"):
            for arg in py_type.__args__:
                if arg is type(None):
                    continue
                return self._python_type_to_json(arg)
        return type_map.get(py_type, "string")

    def to_openai_schema(self) -> dict:
        """转换为 OpenAI tool schema 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolCall:
    """工具调用结果"""

    def __init__(self, tool_call_id: str, name: str, arguments: dict):
        self.tool_call_id = tool_call_id
        self.name = name
        self.arguments = arguments

    def execute(self, tools: dict[str, ToolDefinition]) -> str:
        """执行工具调用"""
        if self.name not in tools:
            return f"Error: Unknown tool '{self.name}'"

        try:
            tool = tools[self.name]
            result = tool.func(**self.arguments)
            return str(result)
        except Exception as e:
            return f"Error: {str(e)}"


def llm_tool(func: Callable[T]) -> Callable[T]:
    """
    装饰器：标记函数为 LLM 工具

    用法:
        @llm_tool
        def get_weather(city: str) -> str:
            '''获取城市天气

            Args:
                city: 城市名称
            '''
            return weather_api.fetch(city)
    """
    # 直接返回原函数，保持可调用性
    # ToolDefinition 会在运行时从函数构建
    return func


class ChatWithToolsMixin:
    """Mixin class providing chat_with_tools method"""

    def chat_with_tools(
        self,
        prompt: str,
        tools: list[Callable],
        *,
        system: str | None = None,
        history: list[dict] | None = None,
        capability: str | None = None,
        model: str | None = None,
        max_tool_calls: int = 10,
        **kwargs,
    ) -> str:
        """
        带工具调用的对话

        Args:
            prompt: 用户提示
            tools: 工具函数列表（用 @llm_tool 装饰）
            system: 系统提示
            history: 对话历史
            capability: 能力标签
            model: 模型名
            max_tool_calls: 最大工具调用次数（防止无限循环）

        Returns:
            str: 最终回复
        """
        # 构建工具映射
        tool_map: dict[str, ToolDefinition] = {}
        for func in tools:
            tool_def = ToolDefinition(func)
            tool_map[tool_def.name] = tool_def

        # 初始消息
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        # 工具调用循环
        for _ in range(max_tool_calls):
            # 调用 LLM
            response = self.chat(
                prompt="",  # 使用 messages
                capability=capability,
                model=model,
                **kwargs,
            )

            # 处理响应（如果是 dict 格式）
            if isinstance(response, dict):
                content = response.get("content", "")
            else:
                content = response

            messages.append({"role": "assistant", "content": content})

            # 检查是否有工具调用
            # 注意：这里需要 LLM 返回 tool_calls 格式
            # 由于兼容性问题，我们用另一种方式：让 LLM 返回 JSON 格式的工具调用
            tool_calls = self._extract_tool_calls(content)

            if not tool_calls:
                # 没有工具调用，返回最终回复
                return content

            # 执行工具调用
            for tc in tool_calls:
                result = tc.execute(tool_map)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.tool_call_id,
                        "content": result,
                    }
                )

        # 达到最大调用次数
        return "工具调用达到最大次数限制"

    def _extract_tool_calls(self, content: str) -> list[ToolCall]:
        """从响应中提取工具调用"""
        # 尝试解析 JSON 数组格式
        try:
            # 查找 JSON 数组
            import re

            match = re.search(r"\[.*?\]", content, re.DOTALL)
            if match:
                calls = json.loads(match.group())
                if isinstance(calls, list):
                    result = []
                    for i, call in enumerate(calls):
                        if isinstance(call, dict) and "name" in call:
                            tc = ToolCall(
                                tool_call_id=str(i),
                                name=call["name"],
                                arguments=call.get("arguments", {}),
                            )
                            result.append(tc)
                    return result
        except Exception:
            pass

        return []


# 为方便使用，也提供独立函数
def chat_with_tools(
    llm_client,
    prompt: str,
    tools: list[Callable],
    **kwargs,
) -> str:
    """
    独立函数版本的 chat_with_tools

    用法:
        from llm_sdk.tools import chat_with_tools
        reply = chat_with_tools(client, "北京天气？", [get_weather])
    """
    mixin = ChatWithToolsMixin()
    # 复制方法
    mixin.chat_with_tools = lambda p, t, **kw: ChatWithToolsMixin.chat_with_tools(
        llm_client, p, t, **kw
    )
    return llm_client.chat_with_tools(prompt, tools, **kwargs)

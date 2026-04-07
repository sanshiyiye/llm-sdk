"""
Python SDK 单元测试
运行: pytest sdk/python/tests/ -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

# ── 测试 errors ──────────────────────────────────────────────────────────────


def test_error_hierarchy():
    from llm_sdk.errors import LLMError, RateLimitError, AuthError, ModelError

    assert issubclass(RateLimitError, LLMError)
    assert issubclass(AuthError, LLMError)
    assert issubclass(ModelError, LLMError)


def test_rate_limit_error_has_retry_after():
    from llm_sdk.errors import RateLimitError

    e = RateLimitError(retry_after=10.0)
    assert e.retry_after == 10.0
    assert e.status_code == 429


def test_structured_output_error_carries_raw():
    from llm_sdk.errors import StructuredOutputError

    e = StructuredOutputError("解析失败", raw_response='{"bad": }')
    assert e.raw_response == '{"bad": }'


# ── 测试 tag 路由 ─────────────────────────────────────────────────────────────


def test_tag_model_map_has_all_capabilities():
    from llm_sdk import TAG_MODEL_MAP

    required = {
        "chat",
        "vision",
        "video-input",
        "embedding",
        "image-gen",
        "fast",
        "local",
    }
    assert required.issubset(set(TAG_MODEL_MAP.keys()))


def test_unknown_capability_raises():
    from llm_sdk.client import _resolve_model

    with pytest.raises(ValueError, match="未知 capability"):
        _resolve_model("nonexistent")


def test_model_param_bypasses_tag(mock_openai):
    from llm_sdk import LLMClient

    c = LLMClient()
    mock_openai.return_value.chat.completions.create.return_value = _make_chat_resp(
        "ok"
    )
    c.chat("hi", model="gpt-chat")
    call_kwargs = mock_openai.return_value.chat.completions.create.call_args
    assert call_kwargs.kwargs["model"] == "gpt-chat"


def test_image_url_triggers_vision_capability(mock_openai):
    from llm_sdk import LLMClient, TAG_MODEL_MAP

    c = LLMClient()
    mock_openai.return_value.chat.completions.create.return_value = _make_chat_resp(
        "ok"
    )
    c.chat("describe", image_url="https://example.com/img.png")
    call_kwargs = mock_openai.return_value.chat.completions.create.call_args
    assert call_kwargs.kwargs["model"] == TAG_MODEL_MAP["vision"]


# ── 测试结构化输出 ─────────────────────────────────────────────────────────────


def test_structured_output_parses_json(mock_openai):
    from pydantic import BaseModel
    from llm_sdk import LLMClient

    class Product(BaseModel):
        name: str
        price: float

    mock_openai.return_value.chat.completions.create.return_value = _make_chat_resp(
        '{"name": "iPhone", "price": 7999.0}'
    )
    c = LLMClient()
    result = c.chat_structured("提取", schema=Product)
    assert result.name == "iPhone"
    assert result.price == 7999.0


def test_structured_output_strips_markdown(mock_openai):
    from pydantic import BaseModel
    from llm_sdk import LLMClient

    class Item(BaseModel):
        value: int

    mock_openai.return_value.chat.completions.create.return_value = _make_chat_resp(
        '```json\n{"value": 42}\n```'
    )
    c = LLMClient()
    result = c.chat_structured("get value", schema=Item)
    assert result.value == 42


def test_structured_output_raises_on_invalid_json(mock_openai):
    from pydantic import BaseModel
    from llm_sdk import LLMClient
    from llm_sdk.errors import StructuredOutputError

    class Item(BaseModel):
        value: int

    mock_openai.return_value.chat.completions.create.return_value = _make_chat_resp(
        "这是一段无法解析的纯文本"
    )
    c = LLMClient()
    with pytest.raises(StructuredOutputError):
        c.chat_structured("get value", schema=Item)


# ── 测试 Session ──────────────────────────────────────────────────────────────


def test_session_maintains_history(mock_openai):
    from llm_sdk import LLMClient

    responses = ["回复1", "回复2"]
    mock_openai.return_value.chat.completions.create.side_effect = [
        _make_chat_resp(r) for r in responses
    ]
    c = LLMClient()
    sess = c.session(system="你是助手")
    r1 = sess.chat("问题1")
    r2 = sess.chat("问题2")
    assert r1 == "回复1"
    assert r2 == "回复2"
    assert sess.turns == 2
    # 第二次调用应该包含第一轮 history
    second_call = mock_openai.return_value.chat.completions.create.call_args_list[1]
    messages = second_call.kwargs["messages"]
    roles = [m["role"] for m in messages]
    assert "system" in roles
    assert roles.count("user") == 2
    assert roles.count("assistant") == 1


def test_session_clear_resets_history(mock_openai):
    from llm_sdk import LLMClient

    mock_openai.return_value.chat.completions.create.return_value = _make_chat_resp(
        "ok"
    )
    c = LLMClient()
    sess = c.session()
    sess.chat("问题1")
    assert sess.turns == 1
    sess.clear()
    assert sess.turns == 0
    assert sess.history == []


def test_session_preserves_system_after_clear(mock_openai):
    from llm_sdk import LLMClient

    mock_openai.return_value.chat.completions.create.return_value = _make_chat_resp(
        "ok"
    )
    c = LLMClient()
    sess = c.session(system="系统提示")
    sess.chat("hi")
    sess.clear()
    sess.chat("hello")
    last_call = mock_openai.return_value.chat.completions.create.call_args
    messages = last_call.kwargs["messages"]
    assert messages[0] == {"role": "system", "content": "系统提示"}


# ── 测试 Tool Use ─────────────────────────────────────────────────────────────


def test_chat_with_tools_executes_tool_loop(mock_openai):
    from llm_sdk import LLMClient, llm_tool

    @llm_tool
    def get_weather(city: str) -> str:
        return f"{city} 晴"

    mock_openai.return_value.chat.completions.create.side_effect = [
        _make_tool_chat_resp("",
                             [{"id": "call_1", "name": "get_weather", "arguments": {"city": "北京"}}]),
        _make_chat_resp("北京今天是晴天"),
    ]

    c = LLMClient()
    reply = c.chat_with_tools("北京天气如何？", tools=[get_weather])

    assert reply == "北京今天是晴天"
    first_call = mock_openai.return_value.chat.completions.create.call_args_list[0]
    assert first_call.kwargs["tools"][0]["function"]["name"] == "get_weather"

    second_call = mock_openai.return_value.chat.completions.create.call_args_list[1]
    messages = second_call.kwargs["messages"]
    assert any(m["role"] == "tool" and m["content"] == "北京 晴" for m in messages)


def test_tool_definition_builds_openai_schema():
    from llm_sdk.tools import ToolDefinition

    def get_weather(city: str, days: int = 1) -> str:
        """获取天气

        Args:
            city: 城市名称
            days: 预报天数
        """

        return f"{city}:{days}"

    schema = ToolDefinition(get_weather).to_openai_schema()
    parameters = schema["function"]["parameters"]
    assert parameters["properties"]["city"]["type"] == "string"
    assert parameters["properties"]["days"]["type"] == "integer"
    assert parameters["required"] == ["city"]


# ── 测试模板 ──────────────────────────────────────────────────────────────────


def test_template_register_and_render():
    from llm_sdk.templates import TemplateRegistry

    reg = TemplateRegistry()
    reg.register("greet", user="用 {lang} 打招呼")
    tmpl = reg.get("greet")
    user, system = tmpl.render(lang="日语")
    assert user == "用 日语 打招呼"
    assert system is None


def test_template_with_system():
    from llm_sdk.templates import TemplateRegistry

    reg = TemplateRegistry()
    reg.register("review", user="审查: {code}", system="你是 {lang} 专家")
    tmpl = reg.get("review")
    user, system = tmpl.render(lang="Python", code="x=1")
    assert "Python" in system
    assert "x=1" in user


def test_template_not_found_raises():
    from llm_sdk.templates import TemplateRegistry
    from llm_sdk.errors import TemplateNotFoundError

    reg = TemplateRegistry()
    with pytest.raises(TemplateNotFoundError):
        reg.get("nonexistent")


def test_template_list():
    from llm_sdk.templates import TemplateRegistry

    reg = TemplateRegistry()
    reg.register("a", user="a")
    reg.register("b", user="b")
    assert set(reg.list()) == {"a", "b"}


def test_template_load_dir(tmp_path):
    from llm_sdk.templates import TemplateRegistry

    (tmp_path / "hello.txt").write_text(
        "system: 你是助手\n---\n你好 {name}", encoding="utf-8"
    )
    (tmp_path / "plain.txt").write_text("纯文本模板 {x}", encoding="utf-8")
    reg = TemplateRegistry()
    count = reg.load_dir(str(tmp_path))
    assert count == 2
    user, system = reg.get("hello").render(name="Claude")
    assert "Claude" in user
    assert system == "你是助手"
    user2, system2 = reg.get("plain").render(x="42")
    assert "42" in user2
    assert system2 is None


# ── 测试错误重试 ──────────────────────────────────────────────────────────────


def test_no_retry_on_auth_error(mock_openai):
    from llm_sdk import LLMClient
    from llm_sdk.errors import AuthError

    err = Exception("Unauthorized")
    err.status_code = 401
    mock_openai.return_value.chat.completions.create.side_effect = err
    c = LLMClient(max_retries=2)
    with pytest.raises(AuthError):
        c.chat("hi")
    # 只调用了 1 次，没有重试
    assert mock_openai.return_value.chat.completions.create.call_count == 1


def test_retry_on_proxy_error(mock_openai):
    from llm_sdk import LLMClient

    err = Exception("Internal Server Error")
    err.status_code = 500
    success = _make_chat_resp("ok")
    mock_openai.return_value.chat.completions.create.side_effect = [err, success]
    c = LLMClient(max_retries=2)
    with patch("time.sleep"):
        result = c.chat("hi")
    assert result["content"] == "ok"
    assert mock_openai.return_value.chat.completions.create.call_count == 2


# ── Fixtures & helpers ────────────────────────────────────────────────────────


@pytest.fixture
def mock_openai():
    with patch("openai.OpenAI") as mock:
        # Configure the mock to return a proper mock client
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock


def _make_chat_resp(content: str):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.choices[0].message.tool_calls = []
    return resp


def _make_tool_chat_resp(content: str, tool_calls: list[dict]):
    resp = _make_chat_resp(content)
    mocked_tool_calls = []
    for tool_call in tool_calls:
        mocked = MagicMock()
        mocked.id = tool_call["id"]
        mocked.type = "function"
        mocked.function.name = tool_call["name"]
        mocked.function.arguments = json.dumps(tool_call.get("arguments", {}), ensure_ascii=False)
        mocked_tool_calls.append(mocked)
    resp.choices[0].message.tool_calls = mocked_tool_calls
    return resp

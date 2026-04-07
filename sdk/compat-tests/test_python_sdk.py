"""
Python SDK 契约测试
运行: pytest sdk/compat-tests/test_python_sdk.py -v
"""

from pathlib import Path
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from llm_sdk import LLMClient, TAG_MODEL_MAP, llm_tool
from llm_sdk.errors import AuthError, StructuredOutputError


@pytest.fixture
def mock_openai():
    with patch("openai.OpenAI") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


def _chat_response(content: str):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.choices[0].message.tool_calls = []
    return resp


def _tool_response(content: str, tool_calls: list[dict]):
    resp = _chat_response(content)
    mocked_tool_calls = []
    for tool_call in tool_calls:
        mocked = MagicMock()
        mocked.id = tool_call["id"]
        mocked.type = "function"
        mocked.function.name = tool_call["name"]
        mocked.function.arguments = json.dumps(
            tool_call.get("arguments", {}), ensure_ascii=False
        )
        mocked_tool_calls.append(mocked)
    resp.choices[0].message.tool_calls = mocked_tool_calls
    return resp


def test_chat_routes_default_and_vision_capability(mock_openai):
    mock_openai.chat.completions.create.return_value = _chat_response("hello")

    client = LLMClient()
    result = client.chat("Hi")
    assert result["content"] == "hello"
    first_call = mock_openai.chat.completions.create.call_args
    assert first_call.kwargs["model"] == TAG_MODEL_MAP["chat"]

    client.chat("describe", image_url="https://example.com/image.png")
    second_call = mock_openai.chat.completions.create.call_args
    assert second_call.kwargs["model"] == TAG_MODEL_MAP["vision"]


def test_chat_with_model_override(mock_openai):
    mock_openai.chat.completions.create.return_value = _chat_response("ok")

    client = LLMClient()
    client.chat("test", model="gpt-4")

    call = mock_openai.chat.completions.create.call_args
    assert call.kwargs["model"] == "gpt-4"


def test_stream_embed_and_image_generation(mock_openai):
    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.text_stream = ["a", "b", "c"]
    mock_openai.chat.completions.stream.return_value = stream

    embedding_resp = MagicMock()
    embedding_resp.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
    mock_openai.embeddings.create.return_value = embedding_resp

    image_resp = MagicMock()
    image_resp.data = [MagicMock(url="https://example.com/image.png")]
    mock_openai.images.generate.return_value = image_resp

    client = LLMClient()

    assert "".join(client.chat_stream("story")) == "abc"
    assert client.embed("hello") == [0.1, 0.2, 0.3]
    assert client.image_gen("cat") == "https://example.com/image.png"


def test_structured_output_contract(mock_openai):
    from pydantic import BaseModel

    class Product(BaseModel):
        name: str
        price: float

    mock_openai.chat.completions.create.return_value = _chat_response(
        '```json\n{"name":"iPhone","price":7999}\n```'
    )

    client = LLMClient()
    result = client.chat_structured("extract", schema=Product)
    assert result.name == "iPhone"
    assert result.price == 7999


def test_structured_output_invalid_json_raises(mock_openai):
    from pydantic import BaseModel

    class Product(BaseModel):
        name: str

    mock_openai.chat.completions.create.return_value = _chat_response("not json")
    client = LLMClient()

    with pytest.raises(StructuredOutputError):
        client.chat_structured("extract", schema=Product)


def test_cache_contract(mock_openai):
    mock_openai.chat.completions.create.return_value = _chat_response("cached")

    client = LLMClient(cache=True)
    first = client.chat("cache me")
    second = client.chat("cache me")

    assert first == {"content": "cached", "_cached": False}
    assert second == {"content": "cached", "_cached": True}
    assert mock_openai.chat.completions.create.call_count == 1


def test_session_keeps_history(mock_openai):
    mock_openai.chat.completions.create.side_effect = [
        _chat_response("first"),
        _chat_response("second"),
    ]

    client = LLMClient()
    session = client.session(system="你是助手")
    first = session.chat("你好")
    second = session.chat("继续")

    assert first == "first"
    assert second == "second"
    second_call = mock_openai.chat.completions.create.call_args_list[1]
    assert len(second_call.kwargs["messages"]) >= 4


def test_tool_use_contract(mock_openai):
    @llm_tool
    def get_weather(city: str) -> str:
        return f"{city} 晴"

    mock_openai.chat.completions.create.side_effect = [
        _tool_response(
            "",
            [{"id": "call_1", "name": "get_weather", "arguments": {"city": "北京"}}],
        ),
        _chat_response("北京今天是晴天"),
    ]

    client = LLMClient()
    reply = client.chat_with_tools("北京天气如何？", tools=[get_weather])

    assert reply == "北京今天是晴天"
    second_call = mock_openai.chat.completions.create.call_args_list[1]
    assert any(
        message["role"] == "tool"
        and message["tool_call_id"] == "call_1"
        and message["content"] == "北京 晴"
        for message in second_call.kwargs["messages"]
    )


def test_error_retry_contract(mock_openai):
    error = Exception("Internal Server Error")
    error.status_code = 500
    mock_openai.chat.completions.create.side_effect = [error, _chat_response("ok")]

    client = LLMClient(max_retries=1)
    with patch("time.sleep"):
        result = client.chat("retry")

    assert result["content"] == "ok"
    assert mock_openai.chat.completions.create.call_count == 2


def test_auth_error_does_not_retry(mock_openai):
    error = Exception("Unauthorized")
    error.status_code = 401
    mock_openai.chat.completions.create.side_effect = error

    client = LLMClient(max_retries=2)
    with pytest.raises(AuthError):
        client.chat("auth")

    assert mock_openai.chat.completions.create.call_count == 1

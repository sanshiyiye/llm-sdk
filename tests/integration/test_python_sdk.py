"""
Integration tests for Python SDK
Run: pytest tests/integration/test_python_sdk.py -v

These tests verify the Python SDK behavior against a mock LLM proxy.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel

from llm_sdk import LLMClient, TAG_MODEL_MAP, client
from llm_sdk.errors import RateLimitError, AuthError, ModelError, StructuredOutputError


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_proxy():
    """Mock the HTTP calls to LiteLLM Proxy."""
    with (
        patch("llm_sdk.client.httpx.post") as mock_post,
        patch("llm_sdk.client.httpx.stream") as mock_stream,
    ):

        def mock_response(status_code=200, json_data=None, text=""):
            resp = MagicMock()
            resp.status_code = status_code
            if json_data:
                resp.json.return_value = json_data
                resp.text = json.dumps(json_data)
            else:
                resp.text = text
            return resp

        yield {"post": mock_post, "stream": mock_stream, "response": mock_response}


# ── Test: Basic chat ─────────────────────────────────────────────────────────


class TestBasicChat:
    def test_chat_returns_string(self, mock_proxy):
        mock_proxy["post"].return_value = mock_proxy["response"](
            json_data={"choices": [{"message": {"content": "Hello!"}}]}
        )

        c = LLMClient()
        result = c.chat("Hi")

        assert isinstance(result, str)
        assert result == "Hello!"

    def test_chat_with_model_override(self, mock_proxy):
        mock_proxy["post"].return_value = mock_proxy["response"](
            json_data={"choices": [{"message": {"content": "ok"}}]}
        )

        c = LLMClient()
        c.chat("test", model="gpt-4")

        call_args = mock_proxy["post"].call_args
        sent_json = json.loads(call_args.kwargs["content"])
        assert sent_json["model"] == "gpt-4"


# ── Test: Capability tag routing ─────────────────────────────────────────────


class TestCapabilityRouting:
    def test_chat_uses_default_capability(self, mock_proxy):
        mock_proxy["post"].return_value = mock_proxy["response"](
            json_data={"choices": [{"message": {"content": "ok"}}]}
        )

        c = LLMClient()
        c.chat("test")

        call_args = mock_proxy["post"].call_args
        sent_json = json.loads(call_args.kwargs["content"])
        assert sent_json["model"] == TAG_MODEL_MAP["chat"]

    def test_fast_capability_routes_to_different_model(self, mock_proxy):
        mock_proxy["post"].return_value = mock_proxy["response"](
            json_data={"choices": [{"message": {"content": "ok"}}]}
        )

        c = LLMClient()
        c.chat("test", capability="fast")

        call_args = mock_proxy["post"].call_args
        sent_json = json.loads(call_args.kwargs["content"])
        assert sent_json["model"] == TAG_MODEL_MAP["fast"]
        assert sent_json["model"] != TAG_MODEL_MAP["chat"]


# ── Test: Vision auto-inference ──────────────────────────────────────────────


class TestVisionInference:
    def test_image_url_triggers_vision_capability(self, mock_proxy):
        mock_proxy["post"].return_value = mock_proxy["response"](
            json_data={"choices": [{"message": {"content": "I see a cat."}}]}
        )

        c = LLMClient()
        c.chat("Describe this", image_url="https://example.com/cat.jpg")

        call_args = mock_proxy["post"].call_args
        sent_json = json.loads(call_args.kwargs["content"])
        assert sent_json["model"] == TAG_MODEL_MAP["vision"]

        # Check image is in messages
        messages = sent_json["messages"]
        assert any("image_url" in str(m) for m in messages)


# ── Test: Error classification ───────────────────────────────────────────────


class TestErrorClassification:
    def test_429_raises_rate_limit_error(self, mock_proxy):
        mock_proxy["post"].return_value = mock_proxy["response"](
            status_code=429, json_data={"error": "Rate limit exceeded"}
        )

        c = LLMClient()
        with pytest.raises(RateLimitError):
            c.chat("test")

    def test_401_raises_auth_error(self, mock_proxy):
        mock_proxy["post"].return_value = mock_proxy["response"](
            status_code=401, json_data={"error": "Unauthorized"}
        )

        c = LLMClient()
        with pytest.raises(AuthError):
            c.chat("test")

    def test_500_raises_model_error(self, mock_proxy):
        mock_proxy["post"].return_value = mock_proxy["response"](
            status_code=500, json_data={"error": "Internal server error"}
        )

        c = LLMClient()
        with pytest.raises(ModelError):
            c.chat("test")


# ── Test: Session history ────────────────────────────────────────────────────


class TestSessionHistory:
    def test_session_maintains_turn_count(self, mock_proxy):
        mock_proxy["post"].return_value = mock_proxy["response"](
            json_data={"choices": [{"message": {"content": "ok"}}]}
        )

        c = LLMClient()
        sess = c.session(system="You are helpful")

        sess.chat("Q1")
        assert sess.turns == 1

        sess.chat("Q2")
        assert sess.turns == 2

    def test_session_includes_history_in_subsequent_calls(self, mock_proxy):
        mock_proxy["post"].return_value = mock_proxy["response"](
            json_data={"choices": [{"message": {"content": "ok"}}]}
        )

        c = LLMClient()
        sess = c.session(system="You are helpful")

        sess.chat("Q1")
        sess.chat("Q2")

        # Check the last call includes both Q1 and Q2
        last_call = mock_proxy["post"].call_args
        sent_json = json.loads(last_call.kwargs["content"])
        messages = sent_json["messages"]

        user_messages = [m for m in messages if m["role"] == "user"]
        assert len(user_messages) == 2


# ── Test: Structured output ──────────────────────────────────────────────────


class TestStructuredOutput:
    def test_structured_output_parses_valid_json(self, mock_proxy):
        class Product(BaseModel):
            name: str
            price: float

        mock_proxy["post"].return_value = mock_proxy["response"](
            json_data={
                "choices": [
                    {"message": {"content": '{"name": "iPhone", "price": 999.0}'}}
                ]
            }
        )

        c = LLMClient()
        result = c.chat_structured("Extract product info", schema=Product)

        assert isinstance(result, Product)
        assert result.name == "iPhone"
        assert result.price == 999.0

    def test_structured_output_strips_markdown(self, mock_proxy):
        class Item(BaseModel):
            value: int

        mock_proxy["post"].return_value = mock_proxy["response"](
            json_data={
                "choices": [{"message": {"content": '```json\n{"value": 42}\n```'}}]
            }
        )

        c = LLMClient()
        result = c.chat_structured("Get value", schema=Item)

        assert result.value == 42


# ── Test: Caching ────────────────────────────────────────────────────────────


class TestCaching:
    def test_cache_returns_cached_response(self, mock_proxy):
        """Same prompt + model should return cached result."""
        mock_proxy["post"].return_value = mock_proxy["response"](
            json_data={"choices": [{"message": {"content": "cached response"}}]}
        )

        c = LLMClient()

        # First call
        r1 = c.chat("test prompt")
        # Second call with same prompt - should hit cache
        r2 = c.chat("test prompt")

        # Only one HTTP call should be made
        assert mock_proxy["post"].call_count == 1
        assert r1 == r2 == "cached response"


# ── Test: Tool use ───────────────────────────────────────────────────────────


class TestToolUse:
    def test_chat_with_tools_executes_function(self, mock_proxy):
        from llm_sdk.tools import llm_tool

        @llm_tool
        def get_weather(city: str) -> str:
            """获取城市天气"""
            return f"{city} is sunny"

        # First call: LLM requests tool
        # Second call: LLM returns final response
        mock_proxy["post"].side_effect = [
            mock_proxy["response"](
                json_data={
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_weather",
                                            "arguments": '{"city": "Beijing"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            ),
            mock_proxy["response"](
                json_data={
                    "choices": [{"message": {"content": "Beijing is sunny today"}}]
                }
            ),
        ]

        c = LLMClient()
        result = c.chat_with_tools(
            "What's the weather in Beijing?", tools=[get_weather]
        )

        assert "sunny" in result
        assert mock_proxy["post"].call_count == 2


# ── Test: Streaming ──────────────────────────────────────────────────────────


class TestStreaming:
    def test_chat_stream_yields_chunks(self, mock_proxy):
        # Mock streaming response
        chunks = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
            b'data: {"choices": [{"delta": {"content": " world"}}]}\n\n',
            b"data: [DONE]\n\n",
        ]

        mock_response = MagicMock()
        mock_response.iter_lines.return_value = chunks
        mock_response.raise_for_status.return_value = None
        mock_proxy["stream"].return_value.__enter__ = MagicMock(
            return_value=mock_response
        )
        mock_proxy["stream"].return_value.__exit__ = MagicMock(return_value=False)

        c = LLMClient()
        chunks_list = list(c.chat_stream("Say hello"))

        assert chunks_list == ["Hello", " world"]


# ── Test: Embeddings ─────────────────────────────────────────────────────────


class TestEmbeddings:
    def test_embed_returns_vector(self, mock_proxy):
        mock_proxy["post"].return_value = mock_proxy["response"](
            json_data={"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        )

        c = LLMClient()
        result = c.embed("test text")

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == 0.1


# ── Test: Image generation ───────────────────────────────────────────────────


class TestImageGeneration:
    def test_image_gen_returns_url(self, mock_proxy):
        mock_proxy["post"].return_value = mock_proxy["response"](
            json_data={"data": [{"url": "https://example.com/image.png"}]}
        )

        c = LLMClient()
        result = c.image_gen("a cat")

        assert result == "https://example.com/image.png"

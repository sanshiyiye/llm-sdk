"""
Doctor 单元测试
运行: pytest sdk/python/tests/test_doctor.py -v
"""

from unittest.mock import MagicMock, patch, call
import pytest


# ── 辅助工具 ──────────────────────────────────────────────────────────────────

def _make_response(status_code: int):
    resp = MagicMock()
    resp.status_code = status_code
    return resp


def _mock_client(readiness_status: int = 200, models_status: int = 200):
    """构造一个 mock httpx.Client，get() 根据 URL 返回不同状态码"""
    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)

    def _get(url, **kwargs):
        if "/health/readiness" in url:
            return _make_response(readiness_status)
        if "/models" in url:
            return _make_response(models_status)
        return _make_response(200)

    mock_client_instance.get.side_effect = _get
    mock_client_instance.close = MagicMock()
    return mock_client_instance


def _mock_client_connect_error():
    """构造一个 get() 抛出 ConnectError 的 mock client"""
    import httpx
    mock_client_instance = MagicMock()
    mock_client_instance.get.side_effect = httpx.ConnectError("refused")
    mock_client_instance.close = MagicMock()
    return mock_client_instance


# ── DoctorResult 基础行为 ──────────────────────────────────────────────────────

def test_doctor_result_ok_when_all_pass():
    from llm_sdk.doctor import DoctorResult, DoctorCheck

    result = DoctorResult(checks=[
        DoctorCheck(name="A", ok=True, message="ok"),
        DoctorCheck(name="B", ok=True, message="ok"),
    ])
    assert result.ok is True


def test_doctor_result_not_ok_when_any_fails():
    from llm_sdk.doctor import DoctorResult, DoctorCheck

    result = DoctorResult(checks=[
        DoctorCheck(name="A", ok=True, message="ok"),
        DoctorCheck(name="B", ok=False, message="fail", fix="fix it"),
    ])
    assert result.ok is False


def test_doctor_result_print_contains_check_names(capsys):
    from llm_sdk.doctor import DoctorResult, DoctorCheck

    result = DoctorResult(checks=[
        DoctorCheck(name="LLM_BASE_URL", ok=True, message="已配置"),
        DoctorCheck(name="鉴权有效", ok=False, message="失败", fix="检查 key"),
    ])
    result.print()
    captured = capsys.readouterr()
    assert "LLM_BASE_URL" in captured.out
    assert "鉴权有效" in captured.out
    assert "检查 key" in captured.out
    assert "✓" in captured.out
    assert "✗" in captured.out


# ── run_doctor 集成行为 ────────────────────────────────────────────────────────

def test_doctor_url_not_set_produces_fail(monkeypatch):
    """未设置 LLM_BASE_URL 时，第一项检查应失败且包含 fix 提示"""
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with patch("httpx.Client", return_value=_mock_client()):
        from llm_sdk.doctor import run_doctor
        result = run_doctor("http://localhost:4000", "no-key", {"fast": "gemini-chat"})

    url_check = next(c for c in result.checks if c.name == "LLM_BASE_URL")
    assert url_check.ok is False
    assert url_check.fix != ""


def test_doctor_key_not_set_produces_fail(monkeypatch):
    """未设置 LLM_API_KEY 时，第二项检查应失败且包含 fix 提示"""
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:4000")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with patch("httpx.Client", return_value=_mock_client()):
        from llm_sdk.doctor import run_doctor
        result = run_doctor("http://localhost:4000", "no-key", {"fast": "gemini-chat"})

    key_check = next(c for c in result.checks if c.name == "LLM_API_KEY")
    assert key_check.ok is False
    assert key_check.fix != ""


def test_doctor_proxy_unreachable_propagates(monkeypatch):
    """Proxy 不可达时，Proxy 可达和鉴权检查都应失败"""
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:4000")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    with patch("httpx.Client", return_value=_mock_client_connect_error()):
        from llm_sdk.doctor import run_doctor
        result = run_doctor("http://localhost:4000", "sk-test", {"fast": "gemini-chat"})

    proxy_check = next(c for c in result.checks if c.name == "Proxy 可达")
    auth_check = next(c for c in result.checks if c.name == "鉴权有效")
    assert proxy_check.ok is False
    assert auth_check.ok is False
    assert "先修复" in auth_check.fix


def test_doctor_auth_failure_401(monkeypatch):
    """Proxy 可达但 /models 返回 401 时，鉴权检查应失败且有 fix 提示"""
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:4000")
    monkeypatch.setenv("LLM_API_KEY", "sk-wrong")

    with patch("httpx.Client", return_value=_mock_client(readiness_status=200, models_status=401)):
        from llm_sdk.doctor import run_doctor
        result = run_doctor("http://localhost:4000", "sk-wrong", {"fast": "gemini-chat"})

    auth_check = next(c for c in result.checks if c.name == "鉴权有效")
    assert auth_check.ok is False
    assert "LITELLM_MASTER_KEY" in auth_check.fix


def test_doctor_all_pass_when_healthy(monkeypatch):
    """所有配置正确时，doctor 应全部通过"""
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:4000")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    with patch("httpx.Client", return_value=_mock_client()):
        from llm_sdk.doctor import run_doctor
        result = run_doctor("http://localhost:4000", "sk-test", {"fast": "gemini-chat"})

    assert result.ok is True


def test_doctor_capability_override_without_provider_prefix_warns(monkeypatch):
    """Capability override 不含 / 也不含 - 时（如裸模型名）应告警"""
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:4000")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL_CHAT", "gpt4o")  # 无 / 也无 -，是错误格式

    with patch("httpx.Client", return_value=_mock_client()):
        from llm_sdk.doctor import run_doctor
        result = run_doctor(
            "http://localhost:4000", "sk-test",
            {"chat": "gpt4o", "fast": "gemini-chat"}
        )

    cap_check = next(c for c in result.checks if c.name == "Capability 配置")
    assert cap_check.ok is False


# ── 通过 LLMClient.doctor() 集成测试 ─────────────────────────────────────────

def test_client_doctor_method_returns_doctor_result(monkeypatch):
    """LLMClient.doctor() 应返回 DoctorResult 实例"""
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:4000")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    with patch("httpx.Client", return_value=_mock_client()):
        from llm_sdk import client
        from llm_sdk.doctor import DoctorResult
        result = client.doctor()

    assert isinstance(result, DoctorResult)
    assert isinstance(result.checks, list)
    assert len(result.checks) >= 4

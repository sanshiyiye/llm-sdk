"""
LLM SDK Doctor - 连接与配置健康检查
=====================================
用法:
    from llm_sdk import client
    result = client.doctor()
    result.print()

    # 或检查是否全部通过
    if not client.doctor().ok:
        raise RuntimeError("LLM SDK 配置异常")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx


@dataclass
class DoctorCheck:
    """单项检查结果"""
    name: str
    ok: bool
    message: str
    fix: str = ""  # 修复建议，仅在 ok=False 时填充


@dataclass
class DoctorResult:
    """doctor() 的完整诊断结果"""
    checks: list[DoctorCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def print(self) -> None:
        """打印人类可读的诊断报告"""
        print("LLM SDK Doctor")
        print("=" * 40)
        for c in self.checks:
            icon = "✓" if c.ok else "✗"
            print(f"{icon}  {c.name:<22} {c.message}")
            if not c.ok and c.fix:
                print(f"   {'':22} → {c.fix}")
        print()
        if self.ok:
            print("全部通过，SDK 可正常使用。")
        else:
            failed = sum(1 for c in self.checks if not c.ok)
            print(f"{failed} 项检查未通过，请按上方提示修复。")


def run_doctor(base_url: str, api_key: str, tag_map: dict[str, str]) -> DoctorResult:
    """执行所有健康检查，返回 DoctorResult。

    设计原则：
    - 每项检查独立执行，前一项失败不跳过后续项
    - 超时设短（5s），doctor 应快速返回
    - 错误消息直接给出 fix hint，不只抛堆栈
    - 禁用系统代理：localhost 请求不应走系统 HTTP 代理
    """
    result = DoctorResult()

    # 禁用系统代理，避免 Windows/Linux 系统代理拦截 localhost 请求
    _transport = httpx.HTTPTransport(proxy=None)
    _client = httpx.Client(transport=_transport, timeout=5.0)

    # ── 1. LLM_BASE_URL 是否配置 ──────────────────────────────────────────────
    url_set = bool(base_url and base_url != "http://localhost:4000")
    env_url = os.getenv("LLM_BASE_URL", "")
    if env_url:
        result.checks.append(DoctorCheck(
            name="LLM_BASE_URL",
            ok=True,
            message=f"已配置 ({base_url})",
        ))
    else:
        result.checks.append(DoctorCheck(
            name="LLM_BASE_URL",
            ok=False,
            message=f"未设置，使用默认值 ({base_url})",
            fix="export LLM_BASE_URL=https://your-proxy.example.com  "
                "（或启动本地 Proxy：docker compose -f proxy/docker-compose.dev.yaml up -d）",
        ))

    # ── 2. LLM_API_KEY 是否配置 ───────────────────────────────────────────────
    env_key = os.getenv("LLM_API_KEY", "")
    if env_key and env_key != "no-key":
        result.checks.append(DoctorCheck(
            name="LLM_API_KEY",
            ok=True,
            message="已配置",
        ))
    else:
        result.checks.append(DoctorCheck(
            name="LLM_API_KEY",
            ok=False,
            message="未设置或使用占位值 'no-key'",
            fix="export LLM_API_KEY=sk-your-team-key  （向平台团队申请）",
        ))

    # ── 3. Proxy 可达性检查 ───────────────────────────────────────────────────
    proxy_reachable = False
    try:
        resp = _client.get(f"{base_url}/health/readiness")
        if resp.status_code < 500:
            proxy_reachable = True
            result.checks.append(DoctorCheck(
                name="Proxy 可达",
                ok=True,
                message=f"HTTP {resp.status_code} /health/readiness",
            ))
        else:
            result.checks.append(DoctorCheck(
                name="Proxy 可达",
                ok=False,
                message=f"HTTP {resp.status_code}，Proxy 返回错误",
                fix="检查 Proxy 服务是否正常运行，查看 Proxy 日志",
            ))
    except httpx.ConnectError:
        result.checks.append(DoctorCheck(
            name="Proxy 可达",
            ok=False,
            message=f"连接被拒绝 ({base_url})",
            fix=(
                "共享 Proxy：确认 LLM_BASE_URL 正确，检查网络/VPN\n"
                "   本地 Proxy：docker compose -f proxy/docker-compose.dev.yaml up -d"
            ),
        ))
    except httpx.TimeoutException:
        result.checks.append(DoctorCheck(
            name="Proxy 可达",
            ok=False,
            message=f"连接超时 ({base_url})",
            fix="检查网络连接，确认 Proxy 地址可从本机访问",
        ))
    except Exception as e:
        result.checks.append(DoctorCheck(
            name="Proxy 可达",
            ok=False,
            message=f"网络错误: {e}",
            fix="检查 LLM_BASE_URL 格式是否正确（需包含 http:// 或 https://）",
        ))

    # ── 4. 鉴权有效性（只有 Proxy 可达时才检查）──────────────────────────────
    # 用 GET /models 验证 key，避免触发实际推理（不依赖具体模型是否可用）
    if proxy_reachable:
        try:
            resp = _client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            if resp.status_code in (200, 201):
                result.checks.append(DoctorCheck(
                    name="鉴权有效",
                    ok=True,
                    message="API key 验证成功",
                ))
            elif resp.status_code in (401, 403):
                result.checks.append(DoctorCheck(
                    name="鉴权有效",
                    ok=False,
                    message=f"HTTP {resp.status_code} 鉴权失败",
                    fix="检查 LLM_API_KEY 是否与 Proxy 端 LITELLM_MASTER_KEY 一致，向平台团队确认",
                ))
            else:
                result.checks.append(DoctorCheck(
                    name="鉴权有效",
                    ok=False,
                    message=f"HTTP {resp.status_code}",
                    fix="查看 Proxy 日志了解详情",
                ))
        except Exception as e:
            result.checks.append(DoctorCheck(
                name="鉴权有效",
                ok=False,
                message=f"请求失败: {e}",
                fix="确认 Proxy 可用后重试",
            ))
    else:
        result.checks.append(DoctorCheck(
            name="鉴权有效",
            ok=False,
            message="跳过（Proxy 不可达）",
            fix="先修复 Proxy 可达性问题",
        ))

    # ── 5. Capability override 合理性检查 ────────────────────────────────────
    # 只对看起来像直接调用 provider 模型（无 / 且无 - 连字符）的覆盖告警。
    # 含 / 的是合法的 provider/model 格式（如 openai/gpt-4o）。
    # 含 - 的是 Proxy 内部路由别名（如 gemini-image-gen、auto-chat），允许使用。
    # 以 auto- 开头的是 Proxy 智能路由，允许使用。
    override_issues = []
    for tag, model in tag_map.items():
        env_key_name = f"LLM_MODEL_{tag.upper().replace('-', '_')}"
        env_val = os.getenv(env_key_name, "")
        if env_val and env_val == model:
            has_slash = "/" in env_val
            has_hyphen = "-" in env_val
            # 没有 / 也没有 - 的短名（如 gpt4o、claude3）很可能是错误格式
            if not has_slash and not has_hyphen:
                override_issues.append(f"{env_key_name}={env_val} 可能不含 provider 前缀")

    if override_issues:
        result.checks.append(DoctorCheck(
            name="Capability 配置",
            ok=False,
            message=f"发现 {len(override_issues)} 个可能有问题的覆盖",
            fix="模型名建议使用 provider/model 格式，如 openai/gpt-4o 或使用默认值",
        ))
    else:
        result.checks.append(DoctorCheck(
            name="Capability 配置",
            ok=True,
            message=f"{len(tag_map)} 个 tag 配置正常",
        ))

    _client.close()
    return result

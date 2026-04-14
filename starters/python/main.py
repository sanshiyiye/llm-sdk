"""
LLM SDK Python Starter
======================
新项目接入 LLM SDK 的最小示例。

使用步骤：
1. 安装依赖：pip install -r requirements.txt
2. 配置环境变量（复制 .env.example 为 .env 并填写）
3. 运行：python main.py
4. 遇到问题：python main.py --doctor
"""

import argparse
import os
import sys

# 优先从 .env 加载配置（需要 python-dotenv）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 未安装时跳过，依赖系统环境变量

from llm_sdk import client


def check_config() -> bool:
    """运行 doctor 检查，返回是否全部通过"""
    result = client.doctor()
    result.print()
    return result.ok


def run_examples():
    """演示 SDK 常用功能"""

    # ── 基础对话 ──────────────────────────────────────────────────────────────
    print("=== 基础对话 ===")
    reply = client.chat("用一句话介绍 Python")
    print(reply["content"])
    print()

    # ── 快速模型（延迟敏感场景）──────────────────────────────────────────────
    print("=== 快速模型 ===")
    reply = client.chat("1+1=?", capability="fast")
    print(reply["content"])
    print()

    # ── 流式输出 ──────────────────────────────────────────────────────────────
    print("=== 流式输出 ===")
    for chunk in client.chat_stream("用三句话介绍大语言模型"):
        print(chunk, end="", flush=True)
    print()
    print()

    # ── 结构化输出 ────────────────────────────────────────────────────────────
    print("=== 结构化输出 ===")
    from pydantic import BaseModel

    class Summary(BaseModel):
        title: str
        points: list[str]

    result = client.chat_structured(
        "总结 Python 的三大优点，返回 title 和 points 列表",
        schema=Summary,
    )
    print(f"标题: {result.title}")
    for p in result.points:
        print(f"  - {p}")
    print()

    # ── 多轮会话 ──────────────────────────────────────────────────────────────
    print("=== 多轮会话 ===")
    session = client.session(system="你是一个简洁的编程助手，每次回答不超过两句话")
    r1 = session.chat("什么是闭包？")
    print(f"Q1 回答: {r1['content']}")
    r2 = session.chat("给一个 Python 例子")
    print(f"Q2 回答: {r2['content']}")


def main():
    parser = argparse.ArgumentParser(description="LLM SDK Python Starter")
    parser.add_argument("--doctor", action="store_true", help="运行健康检查诊断")
    args = parser.parse_args()

    if args.doctor:
        ok = check_config()
        sys.exit(0 if ok else 1)

    # 启动前先做快速健康检查
    result = client.doctor()
    if not result.ok:
        print("⚠️  SDK 配置检查未全部通过，尝试运行示例...\n")
        # 继续运行，让错误自然暴露；或改为 sys.exit(1) 强制退出

    run_examples()


if __name__ == "__main__":
    main()

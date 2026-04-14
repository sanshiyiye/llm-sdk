"""
快速测试脚本 - 运行 SDK doctor 健康检查
用法: python test_doctor.py
"""
import sys
import os

sys.path.insert(0, "sdk/python")

# 先加载 .env，再 import llm_sdk（TAG_MODEL_MAP 在 import 时初始化）
try:
    from dotenv import load_dotenv
    load_dotenv("proxy/.env")
    load_dotenv(".env")
    print("✅ 已加载 .env 配置")
except ImportError:
    print("⚠️  未安装 python-dotenv，依赖系统环境变量")

from llm_sdk import client

print()
result = client.doctor()
result.print()

# 如果全部通过，顺手发一条测试请求
if result.ok:
    print()
    print("发送测试请求...")
    try:
        reply = client.chat("用一句话介绍自己", capability="fast")
        print(f"✅ 响应: {reply['content'][:100]}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")

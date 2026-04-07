# llm-sdk Python

通过 LiteLLM Proxy 统一访问各厂商模型的 Python SDK。

## 功能

- 能力标签路由
- 多轮会话
- 流式输出
- 结构化输出
- Prompt 模板
- Tool Use / Function Calling
- 内存或 Redis 缓存

## 安装

```bash
pip install llm-sdk
```

## 快速开始

```python
from llm_sdk import LLMClient

client = LLMClient()
reply = client.chat("你好")
print(reply["content"])
```

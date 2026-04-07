# @goat/llm-sdk

通过 LiteLLM Proxy 统一访问各厂商模型的 TypeScript SDK。

## 功能

- 能力标签路由
- 多轮会话
- 流式输出
- 结构化输出
- Prompt 模板
- Tool Use / Function Calling
- 内存缓存

## 安装

```bash
npm install @goat/llm-sdk
```

## 快速开始

```ts
import { LLMClient } from '@goat/llm-sdk'

const client = new LLMClient()
const reply = await client.chat('你好')
console.log(reply.content)
```

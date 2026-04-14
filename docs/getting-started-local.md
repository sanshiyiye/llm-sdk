# 本地 Proxy 启动指南

> 适用场景：本地开发、断网环境、自建私有 Proxy

---

## 前置条件

- Docker & Docker Compose
- 至少一个 LLM Provider 的 API Key（OpenAI / Anthropic / Gemini 任一）

---

## 一键启动

```bash
# 1. 复制环境变量模板
cp proxy/.env.example proxy/.env

# 2. 编辑 proxy/.env，填入至少一个 Provider API Key
#    OPENAI_API_KEY=sk-...
#    或 ANTHROPIC_API_KEY=sk-ant-...
#    或 GEMINI_API_KEY=AI...

# 3. 启动本地 Proxy
docker compose -f proxy/docker-compose.dev.yaml up -d

# 4. 等待 readiness（通常 5-10 秒）
curl http://localhost:4000/health/readiness
# 返回 {"status":"healthy"} 即可
```

---

## 配置 SDK 连接本地 Proxy

```bash
export LLM_BASE_URL=http://localhost:4000
export LLM_API_KEY=sk-local-dev   # 与 proxy/.env 中的 LITELLM_MASTER_KEY 一致
```

或创建项目 `.env`：

```env
LLM_BASE_URL=http://localhost:4000
LLM_API_KEY=sk-local-dev
```

---

## 验证本地连接

```python
from llm_sdk import client
result = client.doctor()
result.print()
```

---

## 常用管理命令

```bash
# 查看 Proxy 状态
docker compose -f proxy/docker-compose.dev.yaml ps

# 查看日志
docker compose -f proxy/docker-compose.dev.yaml logs -f

# 停止
docker compose -f proxy/docker-compose.dev.yaml down

# 重启（修改配置后）
docker compose -f proxy/docker-compose.dev.yaml restart
```

---

## 不使用 Docker（直接运行）

```bash
# 安装依赖
pip install "litellm[proxy]"

# 配置环境变量
cp proxy/.env.example proxy/.env
# 编辑 proxy/.env

# 启动
python proxy/start_proxy.py
```

---

## 切换回共享 Proxy

本地开发完成后，只需更新环境变量即可，SDK 代码无需任何改动：

```bash
export LLM_BASE_URL=https://your-shared-proxy.example.com
export LLM_API_KEY=sk-team-abc123
```

---

## 常见问题

**Q: 启动后 `/health/readiness` 返回 503？**  
A: Proxy 尚未完成初始化，等待 10-15 秒后重试。如持续失败，运行 `docker compose -f proxy/docker-compose.dev.yaml logs` 查看错误。

**Q: 请求返回 401？**  
A: 检查 `LLM_API_KEY` 是否与 `proxy/.env` 中的 `LITELLM_MASTER_KEY` 一致。

**Q: 请求返回 404 模型不存在？**  
A: 检查 `proxy/config/config.yaml` 中是否配置了对应的模型，以及对应的 Provider API Key 是否已填写。

**Q: 我没有任何 Provider Key 怎么办？**  
A: 联系平台团队申请共享 Proxy 接入（推荐）。本地 Proxy 需要至少一个有效的 Provider Key。

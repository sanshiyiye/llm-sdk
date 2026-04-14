# Linux 服务器部署指南

本文档面向平台团队，介绍如何在 Linux 服务器上部署 LiteLLM Proxy 供团队共享使用。

---

## 前提条件

服务器上需要安装：

```bash
# Docker（20.10+）
curl -fsSL https://get.docker.com | sh

# Docker Compose Plugin（通常随 Docker 一起安装）
docker compose version
```

---

## 首次部署

### 1. 克隆仓库

```bash
git clone <your-repo-url> llm-sdk
cd llm-sdk/proxy
```

### 2. 配置环境变量

```bash
cp .env.prod.example .env.prod
```

编辑 `.env.prod`，填写真实的 API key：

```bash
# 必填：Proxy 鉴权主密钥（团队成员用这个 key 连接 Proxy）
LITELLM_MASTER_KEY=sk-your-master-key

# 至少填一个 Provider key
SILICONFLOW_API_KEY=sk-...
OPENAI_API_KEY=sk-...
```

> `.env.prod` 包含敏感信息，已在 `.gitignore` 中，**不要提交到 git**。

### 3. 启动服务

```bash
docker compose --env-file .env.prod up -d
```

### 4. 验证启动成功

```bash
# 查看容器状态
docker compose ps

# 检查健康状态（healthy 表示正常）
docker inspect llm-proxy --format='{{.State.Health.Status}}'

# 或直接测试端点
curl http://localhost:4000/health/readiness
```

### 5. 告知团队成员

团队成员在自己的项目里配置：

```bash
LLM_BASE_URL=http://<服务器IP>:4000
LLM_API_KEY=<LITELLM_MASTER_KEY 的值>
```

---

## 日常运维

### 查看日志

```bash
# 实时日志
docker compose logs -f

# 最近 100 行
docker compose logs --tail=100
```

### 重启服务

```bash
docker compose --env-file .env.prod restart
```

### 停止服务

```bash
docker compose --env-file .env.prod down
```

---

## 更新配置（config.yaml）

修改 `proxy/config/config.yaml` 后，需要重启 Proxy 使配置生效：

```bash
# 在服务器上拉取最新代码
git pull

# 重启（不需要重新 pull 镜像）
docker compose --env-file .env.prod restart
```

---

## 升级 Proxy 版本

```bash
# 修改 docker-compose.yaml 中的镜像版本号
# image: ghcr.io/berriai/litellm:v1.83.3  →  改为新版本

# 拉取新镜像并重启
docker compose --env-file .env.prod pull
docker compose --env-file .env.prod up -d
```

---

## 更换 API Key

直接编辑 `.env.prod`，然后重启：

```bash
vim .env.prod
docker compose --env-file .env.prod up -d
```

---

## 诊断问题

从业务代码侧运行：

```bash
python test_doctor.py
```

从服务器侧直接检查：

```bash
# Proxy 是否可达
curl http://localhost:4000/health/readiness

# API key 是否有效
curl -H "Authorization: Bearer <LITELLM_MASTER_KEY>" \
  http://localhost:4000/models
```

---

## 开机自启

Docker 的 `restart: always` 策略已配置，服务器重启后容器会自动启动，无需额外配置。

验证：

```bash
sudo systemctl status docker   # Docker 服务本身需要开机自启
sudo systemctl enable docker   # 如果未启用，执行此命令
```

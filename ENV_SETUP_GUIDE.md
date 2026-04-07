# 🔐 环境变量配置指南

## 📋 概述

本项目已配置为使用 `.env` 文件管理敏感信息，确保 API 密钥等机密数据不会提交到版本控制。

## 🚀 快速开始

### 1. 配置环境变量

编辑 `proxy/.env` 文件，填入你的真实 API 密钥：

```bash
# LiteLLM Proxy 主密钥（必填 - 设置任意字符串作为你的主密钥）
LITELLM_MASTER_KEY=your-secret-master-key

# 第三方 API 密钥（根据你需要使用的模型填写）
OPENAI_API_KEY=sk-your-openai-api-key
ANTHROPIC_API_KEY=sk-your-anthropic-api-key
GEMINI_API_KEY=your-gemini-api-key
SILICONFLOW_API_KEY=sk-your-siliconflow-api-key
```

### 2. 验证配置

运行测试脚本验证环境变量是否正确加载：

```bash
python test_env_setup.py
```

### 3. 启动服务

```bash
python proxy/start_proxy.py
```

## 🔧 技术实现

### 环境变量加载机制

`proxy/start_proxy.py` 已实现以下功能：

1. **自动加载 `.env` 文件**：使用 `python-dotenv` 库
2. **优先级设置**：系统环境变量 > `.env` 文件 > 默认值
3. **安全显示**：敏感信息只显示后4位
4. **错误处理**：优雅处理缺失的环境变量

### 代码示例

```python
# 加载 .env 文件
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ 已加载环境变量文件: {env_path}")

# 获取 API 密钥（支持环境变量优先级）
openai_api_key = os.getenv("OPENAI_API_KEY") or "sk-your-openai-key-here"
```

## ⚠️ 安全注意事项

### ✅ 正确做法

- **使用 `.env` 文件**：所有敏感信息放在 `.env` 文件中
- **保持 `.gitignore` 配置**：`.env` 已正确配置在 `.gitignore` 中
- **使用占位符**：示例配置使用安全的占位符
- **定期轮换密钥**：定期更新 API 密钥

### ❌ 避免做法

- **不要硬编码密钥**：切勿在源代码中直接写入 API 密钥
- **不要提交 `.env` 文件**：确保 `.env` 不会被提交到 Git
- **不要使用弱密钥**：使用强密码作为主密钥
- **不要共享密钥**：每个开发者使用自己的环境配置

## 🔍 故障排除

### 环境变量未加载

1. **检查文件存在**：确认 `.env` 文件存在
2. **检查文件格式**：确保使用 UTF-8 编码
3. **检查变量名**：确认变量名拼写正确
4. **运行测试**：使用 `test_env_setup.py` 验证

### API 密钥无效

1. **检查密钥格式**：确认 API 密钥格式正确
2. **检查服务状态**：确认对应的服务可用
3. **检查网络连接**：确认可以访问外部 API
4. **查看日志**：检查控制台输出获取详细信息

## 📚 相关文件

- `proxy/.env` - 本地环境变量文件（不提交）
- `proxy/.env.example` - 环境变量模板
- `proxy/start_proxy.py` - 环境变量加载实现
- `test_env_setup.py` - 环境变量测试脚本
- `.gitignore` - Git 忽略配置

## 🤝 支持

如有问题，请检查：
1. 环境变量是否正确设置
2. API 密钥是否有效
3. 网络连接是否正常
4. 查看控制台输出获取详细错误信息

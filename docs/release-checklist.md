# SDK 发布检查清单

每次发布三语言 SDK 前，按此清单逐项确认。

---

## 发布前检查

### 1. 三语言功能一致性

- [ ] Python `sdk/python/` — 新功能已实现
- [ ] TypeScript `sdk/typescript/` — 新功能已实现
- [ ] Go `sdk/go/` — 新功能已实现
- [ ] `AGENTS.md` 中 **CODE MAP** 表格已更新（如有新方法）

### 2. 测试通过

```bash
# Python 单元测试
cd sdk/python && pytest tests/ -v

# TypeScript 单元测试
cd sdk/typescript && npm test

# Go 单元测试
cd sdk/go && go test ./... -v

# 三语言契约测试（需要 Proxy 运行）
cd sdk/python && pytest ../compat-tests/test_python_sdk.py -v
cd sdk/typescript && npx vitest run --config vitest.compat.config.ts
cd sdk/compat-tests && go test -v ./...
```

- [ ] Python 单元测试全部通过
- [ ] TypeScript 单元测试全部通过
- [ ] Go 单元测试全部通过
- [ ] 三语言契约测试全部通过

### 3. Doctor 检查

```bash
python test_doctor.py
```

- [ ] doctor() 5 项全部通过
- [ ] `client.chat()` 实际请求成功

### 4. Capability Tag 验证

- [ ] `proxy/config/config.yaml` 中所有 capability 别名已正确配置
- [ ] 无已下线模型作为主路由（允许出现在 fallback 链末尾）
- [ ] fallback 链至少包含 2 个可用 provider

### 5. 文档更新

- [ ] `README.md` 示例与当前 API 一致
- [ ] `AGENTS.md` **CODE MAP** 与实现一致
- [ ] 新的 capability tag（如有）已更新到 `sdk/compat-tests/contract_matrix.md`

### 6. Starter 模板同步

- [ ] `starters/python/main.py` — 示例使用的 API 与最新 SDK 一致
- [ ] `starters/typescript/main.ts` — 同上
- [ ] `starters/go/main.go` — 同上

---

## 发布步骤

### Python

```bash
cd sdk/python

# 确认版本号
grep version pyproject.toml

# 构建
python -m build

# 发布到内部 PyPI（替换为实际仓库地址）
twine upload --repository internal dist/*
```

### TypeScript

```bash
cd sdk/typescript

# 确认版本号
grep '"version"' package.json

# 构建
npm run build

# 发布到内部 npm registry（替换为实际仓库地址）
npm publish --registry https://your-npm.example.com
```

### Go

Go 模块通过 git tag 发布，无需单独构建步骤：

```bash
# 确认 go.mod 中的 module 路径正确
head -3 sdk/go/go.mod

# 打 tag（替换版本号）
git tag sdk/go/v1.x.y
git push origin sdk/go/v1.x.y
```

---

## 发布后验证

- [ ] 从新版本安装 SDK，运行快速验证：
  ```bash
  # Python
  pip install --upgrade llm-sdk
  python -c "from llm_sdk import client; print(client.doctor().ok)"

  # TypeScript
  npm install @goat/llm-sdk@latest
  # 运行 starters/typescript/main.ts

  # Go
  go get github.com/goat/llm-sdk/sdk/go@latest
  ```

- [ ] 通知业务团队新版本发布（在内部渠道同步 CHANGELOG）

---

## 回滚

如果发布后发现严重问题：

```bash
# Python — 固定旧版本
pip install llm-sdk==<last-good-version>

# TypeScript
npm install @goat/llm-sdk@<last-good-version>

# Go — 在 go.mod 中固定旧 tag
go get github.com/goat/llm-sdk/sdk/go@<last-good-tag>
```

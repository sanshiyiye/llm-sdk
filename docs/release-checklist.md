# v1.0.0 发布检查清单

## 发布前

- 确认仓库内组织名已统一为 `goat`
- 确认 `sdk/python/pyproject.toml` 与 `sdk/typescript/package.json` 版本号为 `1.0.0`
- 确认 `sdk/go/go.mod` 模块路径为 `github.com/goat/llm-sdk/sdk/go`
- 确认 `proxy/config/config.yaml` 与 `proxy/k8s/litellm/configmap.yaml` 已同步
- 确认 GitHub Secrets 已配置发布凭证
- 确认 `.github/release.yml` 已配置自动 Release Notes 分类
- 确认 `.github/workflows/docs.yml` 可将文档发布到 GitHub Pages

## 本地验证

```bash
python scripts/release_check.py
```

## 手动抽查

- Python 安装说明与仓库链接正确
- TypeScript 包名为 `@goat/llm-sdk`
- Go 示例导入路径为 `github.com/goat/llm-sdk/sdk/go`
- Proxy Secret 模板包含 Langfuse、DATABASE_URL、SiliconFlow 变量
- 文档站点入口为 `https://goat.github.io/llm-sdk/`
- Release 页面包含自动生成的版本摘要与发布产物信息

## 发布动作

```bash
git tag v1.0.0
git push origin v1.0.0
```

## 发布后确认

- GitHub Actions `release` 工作流成功
- GitHub Actions `docs` 工作流成功
- Python `dist/` 产物已生成
- npm 包产物已上传到 GitHub Release
- Go 测试通过
- SDK compat 报告全绿
- GitHub Release 已生成自动说明并附带 Python / TypeScript 制品
- GitHub Pages 文档首页可正常访问

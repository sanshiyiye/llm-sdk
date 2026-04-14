# 契约矩阵

| 能力 | Python | TypeScript | Go |
|---|---|---|---|
| 默认 chat 路由 | 已覆盖 | 已覆盖 | 已覆盖 |
| vision 自动推断 | 已覆盖 | 已覆盖 | 暂未覆盖 |
| 显式 model 覆盖 | 已覆盖 | 已覆盖 | 已覆盖 |
| Session history | 已覆盖 | 已覆盖 | 已覆盖 |
| 流式输出 | 已覆盖 | 已覆盖 | 暂未覆盖 |
| Structured Output | 已覆盖 | 已覆盖 | 已覆盖 |
| Tool Use | 已覆盖 | 已覆盖 | 已覆盖 |
| 缓存命中 | 已覆盖 | 已覆盖 | 已覆盖 |
| 401/403 不重试 | 已覆盖 | 已覆盖 | 已覆盖 |
| Doctor 健康检查 | 已覆盖 | 已覆盖 | 已覆盖 |
| Doctor URL 未配置 | 已覆盖 | 已覆盖 | 已覆盖 |
| Doctor Proxy 不可达 | 已覆盖 | 已覆盖 | 已覆盖 |
| Doctor 鉴权失败 | 已覆盖 | 已覆盖 | 已覆盖 |
| Doctor 全部通过 | 已覆盖 | 已覆盖 | 已覆盖 |

## 已知差异

- TypeScript 额外支持 `reasoning` capability
- Go 当前没有 `image_gen` 公共 API
- Go 当前 `ChatWithTools` 只接收单个工具实例，不是工具数组
- Go `Doctor.OK()` 是方法调用，Python/TypeScript 是属性

## Onboarding Contract

所有 SDK 必须满足：

- [ ] 仅设置 `LLM_BASE_URL` + `LLM_API_KEY` 即可完成首次 `chat()` 调用
- [ ] `doctor()` 返回结构化结果，包含 `ok` 状态和每项 `fix` 提示
- [ ] Proxy 不可达时，`doctor()` 不抛异常，返回失败的检查项
- [ ] 401/403 错误不重试
- [ ] `local` capability 在 TAG_MODEL_MAP 中存在但标记为仅开发

## Starter 模板一致性

每个语言的 starter 需包含：
- `main.py` / `main.ts` / `main.go` — 演示文件
- `.env.example` — 最小配置模板（仅 BASE_URL + API_KEY）
- `requirements.txt` / `package.json` / `go.mod` — 依赖声明
- 支持 `--doctor` 参数运行健康检查
- 支持 shared proxy / local proxy 两种运行方式（通过环境变量切换）

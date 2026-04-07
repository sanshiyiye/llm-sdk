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

## 已知差异

- TypeScript 额外支持 `reasoning` capability
- Go 当前没有 `image_gen` 公共 API
- Go 当前 `ChatWithTools` 只接收单个工具实例，不是工具数组

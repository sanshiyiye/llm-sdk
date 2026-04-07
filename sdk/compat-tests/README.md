# SDK 契约测试

当前目录用于验证三语言 SDK 的公共行为契约，而不是各语言的内部实现细节。

## 当前覆盖

- 默认 chat 路由
- vision 自动推断
- 显式 model 覆盖
- 多轮会话 history 传递
- 流式输出
- structured output
- Tool Use / Function Calling
- 缓存命中
- 鉴权错误不重试

## 运行方式

### Python

```bash
pytest sdk/compat-tests/test_python_sdk.py -v
```

### TypeScript

```bash
cd sdk/typescript
npm run test:compat:types
npm run test:compat
```

### Go

```bash
cd sdk/compat-tests
go test -v
```

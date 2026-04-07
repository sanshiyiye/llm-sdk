# Proxy 监控手册

## 指标入口

- 应用指标：`http://litellm-proxy.llm-system:9090/metrics`
- 健康检查：`/health/liveliness`、`/health/readiness`
- Langfuse：请求链路、模型调用成功率、延迟与错误明细

## 关键监控项

- `litellm_requests_total`
- `litellm_tokens_total`
- `litellm_request_duration_seconds`
- Deployment ready replicas
- HPA 当前副本数
- Pod restarts
- PostgreSQL 连接可用性

## 告警建议

- 5 分钟错误率 > 2%
- P95 延迟 > 10s
- Pod restart 次数在 10 分钟内 > 3
- readiness 连续失败 > 2 次
- PostgreSQL 不可达
- Langfuse callback 连续失败

## 日常排查

```bash
kubectl top pods -n llm-system
kubectl logs deploy/litellm-proxy -n llm-system --tail=200
kubectl describe hpa litellm-proxy -n llm-system
```

## 发布后观测窗口

- 发布后前 30 分钟重点观察错误率与 P95
- 发布后 24 小时观察模型回退比例与重试比例
- 若 Langfuse 事件量明显下降，优先检查 Secret 与 callback 配置

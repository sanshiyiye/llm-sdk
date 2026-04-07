# Proxy 升级手册

## 升级前检查

- 当前分支测试通过
- `python scripts/generate_k8s_configmap.py` 已执行
- Secret 中所需新增字段已补齐
- PostgreSQL 与 Langfuse 可达

## 升级步骤

```bash
kubectl apply -k proxy/k8s/
kubectl rollout status deployment/litellm-proxy -n llm-system
```

## 配置变更同步

```bash
python scripts/generate_k8s_configmap.py
git diff proxy/config/config.yaml proxy/k8s/litellm/configmap.yaml
```

## 灰度建议

- 先在测试命名空间部署同版本
- 验证 chat、stream、embed、image-gen、tool use
- 再在生产执行滚动升级

## 升级后验收

- SDK compat 测试通过
- `/health/readiness` 正常
- Prometheus 指标恢复
- Langfuse 能看到新请求
- PostgreSQL 审计记录持续写入

## 不兼容变更处理

- 新增模型前先更新 `proxy/config/config.yaml`
- 新增 Secret 字段前先更新 `secret.yaml.example` 与 SealedSecret 模板
- 若发现上游模型能力变化，优先更新契约测试矩阵

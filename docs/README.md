# 文档导航

> Metis 诊断引擎的完整技术文档，分 8 个主题，每个文档独立可读。

---

## 文档清单

| # | 文档 | 主题 |
|---|---|---|
| 1 | [architecture.md](architecture.md) | 系统全景 · 数据流 · 模块依赖 |
| 2 | [taxonomy.md](taxonomy.md) | 25 个 v1 诊断标签详细说明 |
| 3 | [kb-schema.md](kb-schema.md) | Knowledge Base JSON 字段规范 |
| 4 | [action-schema.md](action-schema.md) | Action JSON 5 字段规范 |
| 5 | [prompt.md](prompt.md) | 诊断 prompt 设计 + 迭代指南 |
| 6 | [api.md](api.md) | HTTP API + 端点 + 响应 schema |
| 7 | [evaluation.md](evaluation.md) | 10 段测试场景 + 评估流程 |
| 8 | [development.md](development.md) | 改动 KB / Prompt / Action 的端到端流程 |
| 9 | [layer-model.md](layer-model.md) | 5 层架构 + 复发信号 + next_layer |

---

## 速查路径

| 你想做 | 看 |
|---|---|
| 5 分钟内跑起来 | [../README.md](../README.md) |
| 理解项目做什么 | [../README.md](../README.md) |
| 改 1 条 KB | [development.md#改-KB](development.md#改-KB-数据) |
| 加 1 个 v1 标签 | [taxonomy.md#扩展](taxonomy.md#扩展) |
| 重打所有 KB 标签 | [development.md#重打诊断标签](development.md#重打诊断标签) |
| 调整 prompt | [prompt.md](prompt.md) |
| 看 API 响应格式 | [api.md](api.md) |
| 跑端到端测试 | [development.md#端到端](development.md#端到端) |
| 添加测试场景 | [evaluation.md](evaluation.md) |
| 部署到云 | TODO |

---

## 阅读顺序建议（新加入）

1. **[architecture.md](architecture.md)** ← 先建立全景
2. **[taxonomy.md](taxonomy.md)** ← 知道 25 个 v1 标签是什么
3. **[kb-schema.md](kb-schema.md)** ← 知道 KB 长啥样
4. **[action-schema.md](action-schema.md)** ← 知道输出的 action 长啥样
5. **[api.md](api.md)** ← 知道 HTTP 怎么调
6. **[prompt.md](prompt.md)** ← 知道 LLM 怎么被指挥
7. **[development.md](development.md)** ← 知道怎么改
8. **[evaluation.md](evaluation.md)** ← 知道怎么测

---

*整理于 2026-07-06*

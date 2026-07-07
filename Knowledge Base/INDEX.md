# Knowledge Base · 索引

> 111 条结构化知识条目，跨 8 个分类。

> **完整权威文档在 [`docs/`](../docs/README.md)**。这里只列原始数据。

---

## 数据文件

```
01-身份.json            10  条
02-认知.json            15  条
03-学习.json             9  条
04-行动.json            12  条
05-情绪.json            14  条
06-关系与社会.json      14  条
07-系统与策略.json      28  条  ← 最大
08-意义与目的.json       9  条
                  ─────────
                 合计 111  条
```

每条 entry 的字段规范见 [docs/kb-schema.md](../docs/kb-schema.md)。

## 机器生成物（`_eval/`）

| 文件 | 用途 |
|---|---|
| `kb-index.json` | 标签→K-id 反向索引（FastAPI 启动时加载） |
| `prompt-v1.md` | LLM 系统提示词（自包含，24-28 KB） |

通过 [scripts/build_kb_index.py](../scripts/README.md#4-build_kb_indexpy) 和 [scripts/build_prompt.py](../scripts/README.md#5-build_promptpy) 重建。

## 原始题录

- [米提斯.md](米提斯.md) — 原始 110 题录（Water Your Self）

## 归档

- [_archive_graph_v1/](_archive_graph_v1/) — v0 失败的图谱实验归档，不维护

---

## 改这里前

1. 看 [docs/kb-schema.md](../docs/kb-schema.md)
2. 看 [docs/development.md](../docs/development.md#改-KB-数据)
3. 跑 [scripts/audit_kb.py](../scripts/README.md#1-audit_kbpy) 验证

---

*整理于 2026-07-06*

# Graph Schema · 知识库图谱化规范

> v1 · 2026-07-06 · 初版

## 背景

`Water Your Self` 现有 111 条 JSON 知识条目，9 类、~400 条 `related` 引用。要升维为图谱，以便：
- 查询 "X 的所有 `treats` 边"（对策图谱）
- 找到枢纽概念（高入度节点）
- 路径推理（A → Z 的概念链）
- 后续接入 Neo4j / 可视化

## Node（节点）

每个**知识点** = 一个节点。

```json
{
  "id": "K035",
  "label": "拖延",
  "type": "concept",
  "category": "行动",
  "props": { /* 原 JSON 中 id/name/category 以外的全部字段 */ }
}
```

`type` 当前固定为 `concept`，预留 `category` / `question` / `event` 等扩展。

## Edge（边）

每条 `related` 引用 = 至少一条边。

```json
{
  "source": "K060",
  "target": "K035",
  "type": "treats",
  "weight": 1.0,
  "context": "K060"
}
```

| 字段 | 含义 |
|---|---|
| `source` / `target` | 关系两端 K-id；构成有向边 |
| `type` | 见下表边类型 |
| `weight` | 0..1 强度；v1 默认 1.0，人工标注后调整 |
| `context` | 引用出现的原 entry_id（用于追溯） |

### 边类型（type taxonomy）

| type | 含义 | v1 自动启发 | 后续 |
|---|---|---|---|
| `treats` | A 是 B 的干预 / 对策 | 若 A.interventions 含 B.name → treats | 人工校验 |
| `enables` | A 让 B 更可能 | — | 人工标注 |
| `causes` | A 引起 B | — | 人工标注 |
| `prevents` | A 阻止 / 缓解 B | — | 人工标注 |
| `part_of` | A 是 B 的子集 | — | 人工标注 |
| `contrasts` | A 与 B 形成对照 | — | 人工标注 |
| `related` | 泛指相关（兜底） | 默认 | 留兜底 |

### 去重

`(min(source,target), max(source,target), type)` 三元组唯一；同一对节点上的多种关系各留一条。

## Graph JSON（输出）

```json
{
  "version": "1.0",
  "generated_at": "<ISO8601 UTC>",
  "source_kb_path": "Knowledge Base/",
  "stats": {
    "nodes": 111,
    "edges": <count>,
    "categories": 8,
    "edge_types": ["related", "treats", ...]
  },
  "nodes": [ ... ],
  "edges": [ ... ]
}
```

## 用法

| 工具 | 接入方式 |
|---|---|
| **Neo4j** | 节点标签 = `id`；关系类型 = `type`；`LOAD CSV` 或 APOC |
| **Cytoscape.js** | 直接 `cy.add(nodes)` / `cy.add(edges)`；力导向 + category 着色 |
| **Gephi** | 写 `to_gexf.py`（待做） |
| **jq 查询** | 任何 shell 工具都能遍历 |

## 演化路线

| Phase | 交付 | 状态 |
|---|---|---|
| 1 | 本 SPEC 落地 | ✅ |
| 2 | 转换脚本 + graph.json | ✅ |
| 3 | 人工遍历 ~400 边，标 type 与 weight | ⏳ |
| 4 | MVP 可视化（Cytoscape.js / Gephi） | ⏳ |
| 5 | Neo4j 持久化（如需） | ⏳ |

---

*由 米提斯（Metis）整理。*

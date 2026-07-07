# Knowledge Base JSON Schema

> 111 条知识条目，每条一份 JSON，共 8 个分类文件。

## 1. 文件结构

```
Knowledge Base/
├── 01-身份.json         ← 10 条
├── 02-认知.json         ← 15 条
├── 03-学习.json         ← 9 条
├── 04-行动.json         ← 12 条
├── 05-情绪.json         ← 14 条
├── 06-关系与社会.json   ← 14 条
├── 07-系统与策略.json   ← 28 条  (最大)
└── 08-意义与目的.json   ← 9 条
                       ─────────
                  合计 111 条
```

每个文件是 JSON array：`[{entry1}, {entry2}, ...]`。

## 2. 单条 Entry Schema

```json
{
  "id":                     "K035",
  "name":                   "拖延",
  "category":               "行动",
  "summary":                "拖延不是懒，是情绪管理失败（怕失败/求完美/怕无聊）。",
  "diagnosis_tags":         ["拖延"],
  "trigger":                ["任务有情绪重量", "时限未到"],
  "symptoms":               ["收藏很多课程不练", "迟迟不行动", "等状态"],
  "root_causes":            ["情绪回避", "完美主义前置"],
  "interventions": [
    {
      "label": "5秒起跑",
      "do":    "倒数5秒立刻打开文档输入第一句(不限好坏)",
      "when":  "now",
      "min":   1,
      "mark":  "你输出了第一句(烂也算赢)"
    }
  ],
  "reflection_questions":   ["今天真正阻止我的到底是什么？"],
  "related":                ["K036", "K060", "K062", "K018"]
}
```

## 3. 字段细则

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `id` | string | ✓ | `K` + 数字，或 `K###A`/`K###B`（重复时加后缀） |
| `name` | string | ✓ | 中文名，2-20 字 |
| `category` | enum | ✓ | 8 类之一，见 §1 文件结构 |
| `summary` | string | ✓ | 一句话本质，30-60 字 |
| `diagnosis_tags` | array | ✓ | 1-3 个 v1 标签（见 [taxonomy.md](taxonomy.md)）+ 0-2 个 free 标签 |
| `trigger` | array | ✓ | 触发场景，1-3 个短语 |
| `symptoms` | array | ✓ | 可观察表现，1-3 个短语 |
| `root_causes` | array | ✓ | 根因机制，1-3 个短语 |
| `interventions` | array | ✓ | **结构化动作对象**（见 [action-schema.md](action-schema.md)），1-3 个，默认 3 |
| `reflection_questions` | array | ✓ | 自省问题，1-2 个 |
| `related` | array | ✓ | 关联 K-id 列表，1-6 个 |

## 4. ID 编号规则

- `K001` 到 `K110`（保留原始 110 题录的位置感）
- 重复题录加 `A`/`B` 后缀（仅 `K046A` 和 `K046B`）
- 历史空号保留（K005 / K087 / K110 都已补回）
- **新条目不要占用空号**——下一个新条目从 `K111` 起

## 5. tag 分类约定

`diagnosis_tags` 字段里：
- **v1 标签**（25 个）：必填至少 1 个，可多个
- **free 标签**：辅助标签，可选 0-2 个；用于更细粒度分类

free 标签例子（出现在 KB 里但不在 25 个 v1 里）：
- `as-if`, `5种恢复`, `RAINE`, `Magic Thinking`, `Metis` 等

服务端 `_validate` 永远让 v1 通过、丢弃 free 之外的幻觉。  
诊断接口响应里**只展示 v1 标签**；free 标签供 KB 内部聚类用。

## 6. interventions 字段（关键）

每个动作是一个对象，**不是字符串**。Schema 在 [action-schema.md](action-schema.md) 单独定义，本字段是它的 array container。

```json
{
  "interventions": [
    {"label":"...", "do":"...", "when":"now|today|this_week", "min":<int>, "mark":"..."}
  ]
}
```

**最小变更原则**：如果你改 KB 的某条目，**只动 `interventions` 字段**是安全的（如果只是想让动作更具体）。

## 7. self-ref 防御

`related` 字段**不允许包含自己的 id**。`scripts/relabel_kb.py` 处理时会自动剔除，但写入时也请检查。

历史上有过 17 个 entry 在 `related` 里包含自己 ID，已被清理。现在 `scripts/audit_kb.py` 会自动检测。

---

## 8. 一致性约束（修改时检查）

| 字段 / 关系 | 检查 |
|---|---|
| `category` ∈ 8 个分类 | 必须匹配文件名 |
| `id` 全局唯一 | 跨 8 文件无重复 |
| `id` 出现在 `related` 里 | 必存在且非自己 |
| `diagnosis_tags` 里的 v1 标签 | 必在 25 个范围内（audit 检查） |
| `interventions[i].when` | ∈ `now` / `today` / `this_week` |
| `interventions[i].min` | 0 或正整数 |
| `interventions` 长度 | 1-3（默认 3） |

## 9. 例子：完整一条合规格 Entry

```json
{
  "id": "K073",
  "name": "脆弱和反脆弱",
  "category": "情绪",
  "summary": "脆弱 = 波动大；反脆弱 = 波动越大越受益。",
  "diagnosis_tags": ["易怒"],
  "trigger": ["过度求稳", "过度风控", "波动加剧"],
  "symptoms": ["小波动也崩", "或另一边过度冒险"],
  "root_causes": ["误把'不波动'当安全"],
  "interventions": [
    {
      "label": "找'小波动暴露'",
      "do": "今天主动做1件让你1%不舒服的事",
      "when": "today",
      "min": 15,
      "mark": "波动暴露1次"
    },
    {
      "label": "不等'完全清楚'",
      "do": "在小信息下做小决策",
      "when": "now",
      "min": 0,
      "mark": "1小决策启动"
    },
    {
      "label": "非对称风险:检视本周1个决定",
      "do": "写了+收益-损失",
      "when": "this_week",
      "min": 5,
      "mark": "1决定检视"
    }
  ],
  "reflection_questions": ["这件事的'波动'会让我变强还是变弱？"],
  "related": ["K032", "K052", "K074", "K025"]
}
```

---

*整理于 2026-07-06*

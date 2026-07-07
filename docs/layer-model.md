# 5 层架构 (Layer Model)

> 知识库的纵向深度。决定诊断响应不只是"动作"，而是"动作 + 框架 + 原则 + 主题"的层叠。
>
> 锁定 v1 · 2026-07-06

## 1. 为什么需要 5 层

```
Problem  →  Method  →  Mental-Model  →  Principle  →  Theme
                  ↑                                     ↑
                  method                                theme
                  立刻能做                              长期身份弧
```

直觉：
- 用户遇到 **Problem**：_"我拖了"_ → 系统给 **Method**：_"5秒起跑"_
- 用户反复出现同样 Problem → **Mental-Model**：_"ABC 模型先看触发"_ 
- 同 Pattern 长期存在 → **Principle**：_"你的方向是不是复利"-**（沃德利地图）**
- 长期身份都不清 → **Theme**：_"你想成为谁（Calling / 身份认同）"*

**v1 设计**：
- 默认推送 layer 1（method）。这是 90% 用户立刻需要的。
- layer 3 / 5（principle / theme）只在 **复发信号**触发时浮现（同 tag 7 天内 ≥ 3 次）。

这让系统从"修当下"成长为"看见长期"。

## 2. 4 个 Layer 定义

| Layer | 定义 | 例子 | 用户拿到它的感受 |
|---|---|---|---|
| **method** | 具体动作动词，"今天/立刻可做" | 5秒起跑 / WOOP / 拒绝默认 | "我有动作了" |
| **mental-model** | 解释现象的框架，"为何如此" | ABC模型 / OODA环 / 自由能 | "我理解了" |
| **principle** | 结构性定律，可跨场景泛用 | 沃德利地图 / 期权 / 凯利 / 复利 | "我看穿了场景" |
| **theme** | 长期身份弧，时间尺度 1 年以上 | Calling / 死亡 / 身份认同 | "我是谁、要去哪" |

## 3. 5 层 vs 用户动作

```
用户:             我拖了
↓
诊断响应:        method   ← actions[0] "5秒起跑" (now, 1m)
下次同 problem:    方法不够
↓
复发信号触发:
诊断响应 + next_layer:  principle  ← K073 反脆弱 / K052 不确定性
                theme     ← K062 身份认同
```

## 4. 111 条 KB 的 layer 分布

```
method         37 条   33%   ← 04-行动大部分 + 部分05情绪
mental-model   32 条   29%   ← 02-认知部分 + 05-情绪大部分 + 01-身份
principle      33 条   30%   ← 07-系统与策略大部分 + 06-关系部分 + 03-学习部分
theme           9 条    8%   ← 08-意义与目的大部分
                                  ← 01-身份部分 (To be human, 身份认同)
```

完整映射见 `Knowledge Base/_eval/layer-mapping.json` 或下表。

### method (37 条) — 立刻能做的动作

K006, K007, K008, K016, K018, K019, K021, K022, K023, K024, K025, K026, K027, K033, K034, K035, K036, K037, K038, K040, K043, K044, K046B, K047, K051, K060, K066, K070, K079, K080, K083, K085, K087, K092, K093, K097, K099

### mental-model (32 条) — 解释现象的框架

K003, K004, K010, K011, K014, K015, K017, K020, K028, K029, K030, K032, K039, K041, K042, K045, K048, K050, K053, K054, K055, K059, K061, K062 (reclassify 可能), K067, K076, K084, K086, K104, K098, K105, K111 (?), ...

实际看 `layer-mapping.json` 完整列表。

### principle (33 条) — 结构性定律

K009, K037, K046A, K049, K052, K056, K058, K063, K064, K065, K068, K069, K071, K072, K073, K074, K077, K078, K081, K082, K088, K091, K094, K095, K096, K100, K102, K103, K107, K108, K109

### theme (9 条) — 长期身份弧

K001, K002, K011, K012, K013, K031, K062, K101, K110

## 5. 复发信号（下次升级机制）

**触发条件**：同一 v1 tag 在 7 天内被点亮 ≥ 3 次。

```python
# app/kb.py
def recurrence_count(tag, within_days=7) -> int: ...
def max_recurrence(tags) -> (tag, count): ...
```

**触发效果**（在 `next_layer` 字段）：
- 不动 `actions[]`（用户的立刻动作不被打扰）
- 添加 `next_layer.principle_entries`（2 条 principle 层 KB）
- 添加 `next_layer.theme_entries`（1 条 theme 层 KB）
- 添加 `next_layer.hint`（说明性提示语）
- 加上计数 `next_layer.count` 和触发的 tag 名

记忆目前**只在进程内**，重启服务端会清空。生产需要持久层（Redis / DB）。MVP 接受这个限制。

## 6. 路由（响应 schema 增量）

`POST /diagnose` 的响应新增字段：

```jsonc
{
  "diagnoses": [...],
  "notes":    "...",
  "fallback": "",
  "next_layer": {
    "triggered":  true,            // 是否复发
    "hot_tag":    "拖延",           // 触发的 tag
    "count":      5,                // 7d 内次数
    "window":     "7d",
    "principle_entries": [
      {"kid":"K073","name":"...","summary":"..."},
      {"kid":"K052","name":"...","summary":"..."}
    ],
    "theme_entries": [
      {"kid":"K062","name":"...","summary":"..."}
    ],
    "hint": "你 7 天内被点亮 '拖延' 5 次——这次看深一层: principle 与 theme。"
  }
}
```

`next_layer.triggered=false` 时，结构化字段可省。

## 7. UI 该怎么响应

UI 渲染：

- `next_layer.triggered=true` 时，在诊断卡片下方加一个"提示卡"：
  - 标题：`这个标签你已被点亮 5 次，这次多看一点`
  - 列出 principle / theme 各条目（kid + name + summary）
  - 可点开 KB 详情（目前 UI 没做，TODO）

## 8. 边界与注意

| 风险 | 处理 |
|---|---|
| 用户 1 次复发 7 次真正不同诊断 | max_recurrence 只看本次涉及的 tag,不会误触发 |
| 进程重启清空 memory 失去 7-day 计数 | 接受 MVP 限制;生产加 Redis |
| principle 推理把所有人引向沃德利 | BFS 限制 2 层深度,仍是诊断相关 |
| 7-day window = 7*24 hours | 当前是简单的 `now - days=7`;边缘场景可能错过 |
| recurrence 计数影响 LLM | **不影响** — 计数纯服务端用,不进 prompt |

## 9. 调整这层的规则

1. **更多 layer**：例如把 "method" 拆成 "tactical" 和 "operational"。需要时扩 — 复审原则：用户感觉不够时再拆。
2. **改触发阈值**：3 次/7 天是启发式。收集真实用户数据后调。
3. **改 BFS 深度**：2 层 deep 是默认。如果某层空，扩到 3 层；如果太多，限到 1。

## 10. 相关代码 / 文件

| 文件 | 角色 |
|---|---|
| `scripts/tag_layers.py` | LAYER_OF 字典,生成 `layer-mapping.json` |
| `Knowledge Base/_eval/layer-mapping.json` | 机器可读 layer 表 |
| `app/kb.py` | `layer_of()`, `recurrence_*()`, `k_ids_at_layer()` |
| `app/main.py` | `_build_next_layer()` 把 layer 信息组装进响应 |
| `scripts/build_kb_index.py` | 现在 include `related` 字段(BFS 需要) |

---

*整理于 2026-07-06*

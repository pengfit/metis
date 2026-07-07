#!/usr/bin/env python3
"""build_prompt.py — generate Knowledge Base/_eval/prompt-v1.md from kb-index.json.

The output is self-contained: copy/paste the system block + user input into any
LLM UI (Claude, GPT, Gemini, etc.) — no APIs to wire up.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent / "Knowledge Base"
INDEX = KB / "_eval" / "kb-index.json"
OUT = KB / "_eval" / "prompt-v1.md"

# Group labels by category (cosmetic, for the prompt)
CATEGORY_ORDER = [
    ("心理感受", ["焦虑", "反刍", "低落", "疲惫", "空虚", "易怒"]),
    ("行为模式", ["拖延", "完美主义", "回避", "过度补偿", "边界模糊", "信息撑到饱和"]),
    ("思维模式", ["极端思维", "信念冲突", "证据失效", "视角固化"]),
    ("关系",      ["关系摩擦", "被动等待"]),
    ("阶段与转折", ["平台期", "转型期", "身份迷茫"]),
    ("意义与系统", ["意义缺失", "死亡焦虑", "复利失灵", "赛道疑问"]),
]


def main() -> None:
    idx = json.loads(INDEX.read_text(encoding="utf-8"))

    tags = idx["v1_taxonomy"]
    tag_to_kids = idx["v1_tag_to_kids"]
    by_id = idx["by_id"]

    # Build taxonomy table
    cat_lines = []
    for cat_name, cat_tags in CATEGORY_ORDER:
        cat_lines.append(f"\n**{cat_name}**")
        for t in cat_tags:
            kids = tag_to_kids.get(t, [])
            count = len(kids)
            label = f"  - `{t}`"
            if kids:
                klist = ", ".join(kids[:5]) + (" …" if len(kids) > 5 else "")
                label += f"  →  {klist}  ({count} 条)"
            else:
                label += "  →  （KB 暂无条目，待补）"
            cat_lines.append(label)

    taxonomy_table = "\n".join(cat_lines)

    # Build inline KB snippet — name + summary + action labels (new schema)
    lines = []
    lines.append("\n### 知识库条目（按 id 排序）\n")
    for kid in sorted(by_id.keys()):
        e = by_id[kid]
        lines.append(f"**{kid} · {e['name']}** ({e['category']})")
        lines.append(f"  summary: {e['summary']}")
        # Preview: action labels only (full actions live in KB; server pulls them)
        labels = []
        for act in e.get("interventions", []) or []:
            if isinstance(act, dict) and act.get("label"):
                labels.append(f"`{act['label']}`")
            elif isinstance(act, str):
                labels.append(f"`{act}`")
        if labels:
            preview = " · ".join(labels)
            lines.append(f"  actions: {preview}")
        lines.append("")

    kb_inline = "\n".join(lines)

    prompt = f"""# 诊断 Prompt v1

> **用法：** 把整个 `<role-and-rules>` 块粘进 LLM 的 System（或角色）位置，把用户描述粘进 `<<USER_INPUT>>` 行，输出 JSON。
> **预期：** 1-3 个 v1 标签 + 对应 K-id。**实际动作由服务端从 KB 拉，不需 LLM 写。**

---

## <role-and-rules>

你是一个**诊断引擎**，专长是把用户用自然语言描述的状态匹配到一组预定义的症状标签，并从知识库中找出对应的具体条目。

### 严格约束

1. **只能从以下 25 个 v1 标签中选 1-3 个**。禁止发明新词，禁止使用 KB 中未注册的标签
2. **宁少勿真**。判断不强就少选 / 不选。`diagnoses: []` 是合法输出
3. **用户语言 → 标签**，不是「反向匹配 KB 概念」。例：用户说「我做不下去怕不够好」→ 匹配 `完美主义`（不是 KB 里某个术语）
4. **每诊断必须有 evidence**，引用用户原话里的具体短语，不要泛说
5. **k_ids 必须真实存在于 KB**，错了就丢弃不要捏造
6. **不输出 interventions / actions**——服务端从 K-id 拉真实结构化动作，LLM 不写
7. **不要给建议**——只诊断，不写"你该怎么做"超规格的话

### 25 个 v1 标签（按类别）

{taxonomy_table}

---

{kb_inline}

---

### 输出格式（**纯 JSON，不加 markdown 代码块包裹**）

```json
{{
  "diagnoses": [
    {{
      "tag":        "<v1 标签，从上面 25 个里>",
      "confidence": <0.0–1.0>,
      "evidence":   "<用户原话里的具体短语>",
      "k_ids":      ["<K-id>", "..."]
    }}
  ],
  "notes":    "<一句话整体说明:覆盖/不足/建议>",
  "fallback": "<只在 diagnoses 为空时填:用户可以尝试的方向>"
}}
```

判断 checklist（输出前自检）：
- [ ] tag 在 25 个 v1 内？不在 → 改
- [ ] k_ids 是真实 KB 中存在的 id？不存在 → 改
- [ ] confidence 合理？接近 1=几乎肯定, 0.5=可能有别解, < 0.4=勉强
- [ ] diagnoses 数组 ≤ 3？多了 → 砍到最强的 3 个
- [ ] **没有** interventions / actions 字段（服务端填充）

</role-and-rules>

---

## <user-prompt>

以下是一位用户用自然语言描述的状态。请按 system 规则输出诊断 JSON。

<<USER_INPUT>>
{{USER_DESCRIPTION}}
<</USER_INPUT>>

---

*由 米提斯（Metis）起草 · 基于 v1 Taxonomy + 111 条 KB（`interventions` 字段是动作对象）·
生成时间：Phase 3 v1·
重生成: KB 变化后跑 `python3 scripts/build_prompt.py`*
"""

    OUT.write_text(prompt, encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT}  ({size_kb:.1f} KB)")
    print(f"  v1 tags: {len(tags)}")
    print(f"  KB entries inlined: {len(by_id)}")


if __name__ == "__main__":
    main()

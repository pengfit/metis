#!/usr/bin/env python3
"""build_kb_index.py — build KB tag index for the diagnosis prompt.

Output: Knowledge Base/_eval/kb-index.json
  - v1_taxonomy: list of 25 canonical labels
  - v1_tag_to_kids: { v1_tag → [K-ids] }
  - free_tags: tag → K-ids (not in v1; useful for fallback / future)
  - by_id: { K-id → { name, category, summary, diagnosis_tags, interventions } }
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent / "Knowledge Base"
OUT = KB / "_eval" / "kb-index.json"

# Mirror of V1_TAGS in relabel_kb.py — keep in sync.
V1_TAGS: set[str] = {
    "焦虑", "反刍", "低落", "疲惫", "空虚", "易怒",
    "拖延", "完美主义", "回避", "过度补偿", "边界模糊", "信息撑到饱和",
    "极端思维", "信念冲突", "证据失效", "视角固化",
    "关系摩擦", "被动等待",
    "平台期", "转型期", "身份迷茫",
    "意义缺失", "死亡焦虑", "复利失灵", "赛道疑问",
}


def main() -> None:
    entries = []
    for p in sorted(KB.glob("0?-*.json")):
        entries.extend(json.load(p.open(encoding="utf-8")))

    by_id: dict[str, dict] = {}
    tag_to_kids: dict[str, list[str]] = defaultdict(list)
    for e in entries:
        by_id[e["id"]] = {
            "name": e.get("name", ""),
            "category": e.get("category", ""),
            "summary": e.get("summary", ""),
            "diagnosis_tags": e.get("diagnosis_tags", []),
            "interventions": e.get("interventions", []),  # structured action objects
            "related": e.get("related", []),
        }
        for t in e.get("diagnosis_tags", []):
            tag_to_kids[t].append(e["id"])

    v1_index = {t: sorted(tag_to_kids.get(t, [])) for t in sorted(V1_TAGS)}
    free_index = {t: sorted(kids) for t, kids in tag_to_kids.items() if t not in V1_TAGS}

    index = {
        "version": 1,
        "stats": {
            "total_entries": len(by_id),
            "v1_tags": len(V1_TAGS),
            "v1_tags_with_coverage": sum(1 for k, v in v1_index.items() if v),
            "free_tags": len(free_index),
        },
        "v1_taxonomy": sorted(V1_TAGS),
        "v1_tag_to_kids": v1_index,
        "free_tags": free_index,
        "by_id": by_id,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    size_kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT}  ({size_kb:.1f} KB)")
    print(f"  entries: {len(by_id)}")
    print(f"  v1 tag coverage: {index['stats']['v1_tags_with_coverage']}/{len(V1_TAGS)}")
    sparse = sorted(
        [(t, len(v)) for t, v in v1_index.items() if 0 < len(v) <= 2],
        key=lambda x: x[0]
    )
    if sparse:
        print(f"  sparse (≤2 entries):")
        for t, c in sparse:
            print(f"    {t:<10} {c}")


if __name__ == "__main__":
    main()

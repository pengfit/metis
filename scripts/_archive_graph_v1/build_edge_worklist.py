#!/usr/bin/env python3
"""build_edge_worklist.py — Knowledge Base/graph.json → edges-to-label.csv.

Produces a UTF-8 (with BOM) CSV that opens cleanly in Numbers / Excel / Sheets.
Edges sorted by combined-degree of source+target (impact-first).

Columns:
  src, tgt, src_label, tgt_label, src_cat, tgt_cat,
  src_summary, tgt_summary, cur_type, new_type, new_weight, hint, note
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent / "Knowledge Base"
SRC = KB / "graph.json"
OUT = KB / "edges-to-label.csv"

VALID_TYPES = {"related", "treats", "enables", "causes", "prevents", "part_of", "contrasts"}

# Cross-category heuristics (helps user get going)
PAIR_HINTS = {
    ("行动", "情绪"): "treats (行动解决情绪)",
    ("行动", "认知"): "treats / applies",
    ("认知", "情绪"): "treats / reframes",
    ("认知", "行动"): "enables (思维驱动行动)",
    ("身份", "行动"): "enables (身份驱动)",
    ("意义与目的", "行动"): "enables / motivates",
    ("意义与目的", "意义与目的"): "related",
    ("行动", "行动"): "同簇，多为 enables / contrasts",
    ("情绪", "情绪"): "同簇，多为 enables / prevents",
    ("认知", "认知"): "同簇，多为 enables / part_of",
}


def hint(src_cat: str, tgt_cat: str) -> str:
    if src_cat == tgt_cat:
        return PAIR_HINTS.get((src_cat, tgt_cat), "related")
    if (src_cat, tgt_cat) in PAIR_HINTS:
        return PAIR_HINTS[(src_cat, tgt_cat)]
    return PAIR_HINTS.get((tgt_cat, src_cat), "相关")


def main() -> None:
    graph = json.load(SRC.open(encoding="utf-8"))
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = graph["edges"]

    deg = Counter()
    for e in edges:
        deg[e["source"]] += 1
        deg[e["target"]] += 1

    rows = []
    for e in edges:
        src = nodes[e["source"]]
        tgt = nodes[e["target"]]
        src_sum = (src["props"].get("summary") or "")[:40].replace("\n", " ")
        tgt_sum = (tgt["props"].get("summary") or "")[:40].replace("\n", " ")
        # Combined-degree: how impactful this edge is (sum of both endpoints' degree)
        impact = deg[e["source"]] + deg[e["target"]]
        rows.append({
            "src": e["source"],
            "tgt": e["target"],
            "src_label": src["label"],
            "tgt_label": tgt["label"],
            "src_cat": src["category"],
            "tgt_cat": tgt["category"],
            "src_summary": src_sum,
            "tgt_summary": tgt_sum,
            "cur_type": e["type"],
            "new_type": "",
            "new_weight": "",
            "hint": hint(src["category"], tgt["category"]),
            "impact": impact,
            "note": "",
        })

    # Stratified sort: group by source-category (so each category opens the file),
    # within group sort by impact DESC. The top of the CSV is no longer all hubs.
    rows.sort(key=lambda r: (r["src_cat"], -r["impact"], r["src"], r["tgt"]))

    fieldnames = list(rows[0].keys())
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    type_counter = Counter(r["cur_type"] for r in rows)
    by_cat = Counter(r["src_cat"] for r in rows)
    print(f"Wrote {OUT.relative_to(KB.parent)}  ({OUT.stat().st_size/1024:.1f} KB)")
    print(f"  rows: {len(rows)}")
    print(f"  sort: 按 src_cat 分组，组内按 impact（度数和）降序")
    print(f"  当前类型分布：")
    for t, c in type_counter.most_common():
        print(f"    {t:<10} {c}")
    print(f"  各分类行数：")
    for cat, c in sorted(by_cat.items()):
        print(f"    {cat:<10} {c}")
    print(f"\n  Valid new_type values: {sorted(VALID_TYPES)}")
    print(f"  • 填 new_type 列；留空表示不修改。")
    print(f"  • new_weight 留空表示保留原值。")
    print(f"  • 完成后跑: python3 scripts/apply_edge_labels.py")


if __name__ == "__main__":
    main()

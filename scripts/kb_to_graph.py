#!/usr/bin/env python3
"""kb_to_graph.py — Knowledge Base (8 JSON files) → property-graph JSON.

Reads every *.json file under ../Knowledge Base/ (except graph.json, INDEX.md
helpers and the schema spec) and emits a single ../Knowledge Base/graph.json
with `nodes` and `edges`.

Edge typing heuristic (v1):
    If entry.interventions mentions another entry.name  →  type = "treats"
    Otherwise                                          →  type = "related"

Deduplication key: (min(src,tgt), max(src,tgt), type)
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB_DIR = HERE.parent / "Knowledge Base"
OUT = KB_DIR / "graph.json"
SCHEMA_PATH = KB_DIR / "graph-schema.md"
SKIP = {"graph.json"}
NODE_FIELDS_STRIPPED = {"id", "name", "category"}


def load_entries() -> dict[str, dict]:
    nodes_by_id: dict[str, dict] = {}
    for path in sorted(KB_DIR.glob("*.json")):
        if path.name in SKIP:
            continue
        with path.open(encoding="utf-8") as f:
            entries = json.load(f)
        for entry in entries:
            if not entry.get("id"):
                continue
            if entry["id"] in nodes_by_id:
                raise SystemExit(f"Duplicate id detected: {entry['id']}")
            nodes_by_id[entry["id"]] = {**entry, "_source_file": path.name}
    return nodes_by_id


def build_nodes(nodes_by_id: dict[str, dict]) -> list[dict]:
    nodes = []
    for entry in nodes_by_id.values():
        props = {k: v for k, v in entry.items() if k not in NODE_FIELDS_STRIPPED and not k.startswith("_")}
        nodes.append(
            {
                "id": entry["id"],
                "label": entry.get("name", ""),
                "type": "concept",
                "category": entry.get("category", ""),
                "props": props,
            }
        )
    return nodes


def is_treats(source: dict, target_name: str) -> bool:
    if not target_name:
        return False
    interventions = source.get("interventions") or []
    pattern = re.compile(re.escape(target_name))
    for itv in interventions:
        if itv and pattern.search(itv):
            return True
    return False


def build_edges(nodes_by_id: dict[str, dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    edges: list[dict] = []
    dangling: list[str] = []

    for src_id, entry in nodes_by_id.items():
        src_name = (entry.get("name") or "").strip()
        related = entry.get("related") or []
        for tgt_id in related:
            if tgt_id == src_id:
                continue  # defensive: skip self-loops
            if tgt_id not in nodes_by_id:
                dangling.append(tgt_id)
                continue
            target = nodes_by_id[tgt_id]
            target_name = (target.get("name") or "").strip()
            edge_type = "treats" if is_treats(entry, target_name) else "related"
            a, b = sorted([src_id, tgt_id])
            key = (a, b, edge_type)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "source": src_id,
                    "target": tgt_id,
                    "type": edge_type,
                    "weight": 1.0,
                    "context": src_id,
                }
            )
    return edges, dangling


def top_connected(nodes: list[dict], edges: list[dict], k: int = 10) -> list[dict]:
    deg: Counter[str] = Counter()
    for e in edges:
        deg[e["source"]] += 1
        deg[e["target"]] += 1
    by_id = {n["id"]: n for n in nodes}
    return [
        {
            "id": nid,
            "label": by_id[nid]["label"],
            "category": by_id[nid]["category"],
            "degree": d,
        }
        for nid, d in deg.most_common(k)
    ]


def main() -> None:
    nodes_by_id = load_entries()
    nodes = build_nodes(nodes_by_id)
    edges, dangling = build_edges(nodes_by_id)

    categories = sorted({n["category"] for n in nodes if n["category"]})
    edge_types = sorted({e["type"] for e in edges})
    type_counts = Counter(e["type"] for e in edges)

    graph = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_kb_path": "Knowledge Base/",
        "schema_ref": "graph-schema.md",
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "categories": len(categories),
            "edge_types": edge_types,
            "edge_type_counts": dict(type_counts),
            "dangling_refs": dangling,
            "avg_degree": round(2 * len(edges) / max(len(nodes), 1), 3),
            "top_connected": top_connected(nodes, edges, 10),
        },
        "nodes": nodes,
        "edges": edges,
    }

    with OUT.open("w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT}")
    print(f"  nodes: {len(nodes)}")
    print(f"  edges: {len(edges)}  (unique dedup'd)")
    print(f"  categories: {categories}")
    print(f"  edge types & counts:")
    for t, c in type_counts.most_common():
        print(f"    {t:<10} {c}")
    print(f"  dangling refs (in `related` but no such node): {dangling}")
    print(f"  top 10 hubs:")
    for h in graph["stats"]["top_connected"]:
        print(f"    {h['id']:<6} ({h['category']:<8})  deg={h['degree']:>2}  {h['label']}")
    if SCHEMA_PATH.exists():
        print(f"  schema: {SCHEMA_PATH.name}")


if __name__ == "__main__":
    main()

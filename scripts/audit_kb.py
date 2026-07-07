#!/usr/bin/env python3
"""audit_kb.py — sanity-check across the entire knowledge-base pipeline.

Reads all eight category JSONs + graph.json + edges-to-label.csv and reports:
  • self-references in any entry's `related` array
  • duplicate entries / duplicate K-ids
  • references to non-existent K-ids (dangling)
  • duplicate entries WITHIN a single entry's related array
  • empty placeholders ([待补])
  • entries missing required fields
  • categorical coverage stats
  • graph.json <-> source JSON drift (if any)
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent / "Knowledge Base"

REQUIRED_FIELDS = {"id", "name", "category", "summary"}
PLACEHOLDER_NAME = "[待补]"


def main() -> int:
    json_paths = sorted(p for p in KB.glob("*.json") if p.name not in {"graph.json"})

    all_entries: list[dict] = []
    for p in json_paths:
        all_entries.extend(json.load(p.open(encoding="utf-8")))

    issues = []

    # 1. Required fields
    for e in all_entries:
        missing = REQUIRED_FIELDS - {k for k in e if e.get(k) not in (None, "")}
        if missing:
            issues.append((f"missing fields {missing} in {e.get('id', '?')} ({e.get('name', '?')})", ""))

    # 2. Placeholders
    placeholders = [e for e in all_entries if e.get("name") == PLACEHOLDER_NAME]
    if placeholders:
        issues.append((f"{len(placeholders)} placeholder entries still present: " + ", ".join(e["id"] for e in placeholders), ""))

    # 3. Duplicate K-ids across files
    id_counter = Counter(e["id"] for e in all_entries)
    dup_ids = [k for k, c in id_counter.items() if c > 1]
    if dup_ids:
        issues.append((f"duplicate K-ids across files: {dup_ids}", ""))

    # 4. Self-references & within-array duplicates & dangling refs
    by_id = {e["id"]: e for e in all_entries}
    self_refs = []
    dup_within = []
    dangling = []
    for e in all_entries:
        rel = e.get("related") or []
        # self-refs
        s = [r for r in rel if r == e["id"]]
        if s:
            self_refs.append((e["id"], s))
        # within-array dupes
        cnt = Counter(rel)
        dup = {k: c for k, c in cnt.items() if c > 1}
        if dup:
            dup_within.append((e["id"], dup))
        # dangling
        d = [r for r in rel if r not in by_id]
        if d:
            dangling.append((e["id"], d))

    if self_refs:
        issues.append((f"{len(self_refs)} entries still self-reference:", self_refs))
    if dup_within:
        issues.append((f"{len(dup_within)} entries have duplicates within `related`:", dup_within))
    if dangling:
        issues.append((f"{len(dangling)} entries reference non-existent K-ids:", dangling))

    # 5. Categorical coverage
    cat_counts = Counter(e["category"] for e in all_entries)
    print("Categorical coverage:")
    for cat, c in sorted(cat_counts.items(), key=lambda x: x[0]):
        marker = "" if c >= 5 else " ⚠ thin"
        print(f"  {cat:<10} {c}{marker}")

    # 6. graph.json drift
    g_path = KB / "graph.json"
    if g_path.exists():
        g = json.load(g_path.open(encoding="utf-8"))
        g_ids = {n["id"] for n in g["nodes"]}
        src_ids = {e["id"] for e in all_entries}
        if g_ids != src_ids:
            extra = g_ids - src_ids
            missing = src_ids - g_ids
            if extra:
                issues.append((f"graph.json has phantom nodes: {extra}", ""))
            if missing:
                issues.append((f"graph.json missing nodes: {missing}", ""))
        # self-loops in graph
        self_loops = [e for e in g["edges"] if e["source"] == e["target"]]
        if self_loops:
            issues.append((f"graph.json has {len(self_loops)} self-loops", ""))
        # dup edges in graph
        ec = Counter((e["source"], e["target"], e["type"]) for e in g["edges"])
        graph_dups = {k: c for k, c in ec.items() if c > 1}
        if graph_dups:
            issues.append((f"graph.json has duplicate edges: {graph_dups}", ""))

    # 7. CSV ↔ graph cross-sync
    csv_path = KB / "edges-to-label.csv"
    if csv_path.exists() and g_path.exists():
        import csv
        with csv_path.open(encoding="utf-8-sig") as f:
            csv_pairs = {(row["src"], row["tgt"]) for row in csv.DictReader(f)}
        g_pairs = {(e["source"], e["target"]) for e in g["edges"]}
        if csv_pairs != g_pairs:
            only_csv = csv_pairs - g_pairs
            only_g = g_pairs - csv_pairs
            if only_csv:
                issues.append((f"CSV has pairs not in graph: {only_csv}", ""))
            if only_g:
                issues.append((f"graph has pairs not in CSV: {only_g}", ""))

    print("")
    if not issues:
        print("✓ ALL CHECKS PASSED. No issues.")
        return 0
    print(f"⚠ {len(issues)} issue(s) found:\n")
    for i, (msg, data) in enumerate(issues, 1):
        print(f"  {i}. {msg}")
        if data:
            for d in data[:8]:
                print(f"     - {d}")
            if len(data) > 8:
                print(f"     … +{len(data) - 8} more")
    return 1


if __name__ == "__main__":
    sys.exit(main())

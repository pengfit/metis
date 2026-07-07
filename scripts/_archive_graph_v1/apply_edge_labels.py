#!/usr/bin/env python3
"""apply_edge_labels.py — apply edge-type/weight labels from edges-to-label.csv.

Reads:     Knowledge Base/edges-to-label.csv
Updates:   Knowledge Base/graph.json
Re-emits:  Knowledge Base/graph.html (via build_graph_html.py)
"""

from __future__ import annotations

import json
import subprocess
import sys
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent / "Knowledge Base"
GRAPH = KB / "graph.json"
CSV_FILE = KB / "edges-to-label.csv"

VALID_TYPES = {"related", "treats", "enables", "causes", "prevents", "part_of", "contrasts"}


def main() -> int:
    if not CSV_FILE.exists():
        print(f"Missing: {CSV_FILE}")
        return 1

    g = json.load(GRAPH.open(encoding="utf-8"))
    edges_by_pair = {(e["source"], e["target"]): e for e in g["edges"]}

    n_total = 0
    n_type_changed = 0
    n_weight_changed = 0
    n_skipped = 0
    n_invalid = 0

    with CSV_FILE.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            src = (row.get("src") or "").strip()
            tgt = (row.get("tgt") or "").strip()
            new_type = (row.get("new_type") or "").strip()
            new_weight = (row.get("new_weight") or "").strip()
            note = (row.get("note") or "").strip()
            if not (new_type or new_weight):
                n_skipped += 1
                continue
            n_total += 1
            edge = edges_by_pair.get((src, tgt))
            if edge is None:
                # CSV row key from upstream side; check the canonical (min,max) too
                a, b = sorted([src, tgt])
                rev = edges_by_pair.get((b, a))
                edge = rev
                if edge is None:
                    print(f"  ⚠ no edge found for {src}→{tgt}")
                    n_invalid += 1
                    continue

            if new_type:
                if new_type not in VALID_TYPES:
                    print(f"  ⚠ invalid type '{new_type}' for {src}→{tgt} → skip")
                    n_invalid += 1
                    continue
                old = edge["type"]
                edge["type"] = new_type
                if old != new_type:
                    n_type_changed += 1

            if new_weight:
                try:
                    w = float(new_weight)
                    if not (0.0 <= w <= 1.0):
                        raise ValueError
                    edge["weight"] = round(w, 3)
                    n_weight_changed += 1
                except ValueError:
                    print(f"  ⚠ invalid weight '{new_weight}' for {src}→{tgt} → skip")
                    n_invalid += 1
                    continue

            if note:
                edge["context_note"] = note  # extra field; preserves annotation

    GRAPH.write_text(
        json.dumps(g, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"✓ Updated graph.json ({n_total} rows applied, {n_invalid} invalid, {n_skipped} skipped).")
    print(f"  type changes: {n_type_changed}    weight changes: {n_weight_changed}")

    # re-emit viz
    print("\nRebuilding graph.html...")
    subprocess.run([sys.executable, str(HERE / "build_graph_html.py")], check=False)

    return 0


if __name__ == "__main__":
    sys.exit(main())

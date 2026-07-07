#!/usr/bin/env python3
"""tag_layers.py — assign each KB entry to one of 4 layers.

Layers (see docs/layer-model.md for full definition):
  - method        tactical "do this now" — primary value = interventions
  - mental-model  explain a phenomenon — value = summary / framework
  - principle     structural law, generalizable — value = insight reuse
  - theme         identity / calling / death — value = long-arc meaning

Layer decides where a K-id surfaces in the response:
  - method always lights up in actions[]
  - principle surfaces when a tag recurs 3+ times in 7 days
  - theme surfaces when pattern is chronic + meaning-arc is the open question

Output: Knowledge Base/_eval/layer-mapping.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent / "Knowledge Base"
OUT = KB / "_eval" / "layer-mapping.json"

LAYERS = ("method", "mental-model", "principle", "theme")


# ──────────────────────────────────────────────────────────────────────────
# 111 entries × 1 layer (manually curated, locked v1)
# ──────────────────────────────────────────────────────────────────────────
LAYER_OF: dict[str, str] = {
    # ── 01-身份 ──
    "K011": "theme",          # To be human — humanity as long-arc identity
    "K014": "mental-model",   # 信念 — framework for understanding belief
    "K015": "mental-model",   # 扮演 — as-if understanding identity
    "K028": "mental-model",   # 自我和谐 — internal conflict framework
    "K029": "mental-model",   # 24种性格 — personality framework
    "K030": "mental-model",   # Find who you are — growth process
    "K045": "mental-model",   # 我生了不是 — narrative reframing
    "K053": "mental-model",   # 3个我 — self-structure
    "K054": "mental-model",   # 君子不器 — T-shape understanding
    "K062": "theme",          # 身份认同 — identity construction (long-arc)

    # ── 02-认知 ──
    "K020": "mental-model",   # E→T→E — CBT framework
    "K046A": "principle",     # 概率 — probabilistic thinking law
    "K047": "method",         # 问自己 — asking questions, tactical
    "K048": "mental-model",   # 叙事 — narrative framing
    "K057": "mental-model",   # SDT — motivation framework
    "K058": "principle",      # 自由能 — Free Energy law
    "K067": "mental-model",   # 偏置 — cognitive biases framework
    "K068": "principle",      # 分布 — distribution thinking law
    "K069": "principle",      # 贝叶斯 — Bayesian update law
    "K070": "method",         # 信息价值 — info triage, tactical
    "K076": "mental-model",   # 偏差 — error types framework
    "K077": "principle",      # 回归均值 — regression-to-mean law
    "K078": "principle",      # 前景理论 — prospect theory law
    "K079": "method",         # OODA — decision cycle, tactical
    "K080": "method",         # 预测 — forecasting practice

    # ── 03-学习 ──
    "K059": "mental-model",   # 高认知负荷 — cognitive load applied
    "K081": "principle",      # 认知负载 — cognitive load theory itself
    "K082": "principle",      # ICAP — learning hierarchy law
    "K083": "method",         # 刻意练习 — deliberate practice, tactical
    "K084": "mental-model",   # 表征/图式 — representation framework
    "K085": "method",         # 综合知识 — cross-domain, tactical
    "K086": "mental-model",   # 默会知识 — tacit knowledge framework
    "K087": "method",         # 反馈 — feedback loop, tactical
    "K088": "principle",      # 可取的困难 — desirable difficulties law

    # ── 04-行动 ──
    "K006": "method",         # 理想+现实+Action
    "K016": "method",         # 环境
    "K021": "method",         # Focus
    "K023": "method",         # Change A/B/C
    "K024": "method",         # 例行公事
    "K025": "method",         # take time off
    "K026": "method",         # 写下来
    "K034": "method",         # Say No
    "K035": "method",         # 拖延
    "K036": "method",         # 完美主义
    "K038": "method",         # 奖励过程
    "K060": "method",         # WOOP

    # ── 05-情绪 ──
    "K003": "mental-model",   # 自尊
    "K004": "mental-model",   # 消极
    "K008": "method",         # 笑 — physical tactical
    "K010": "mental-model",   # 幸福水平回归
    "K017": "mental-model",   # P or N 视角 — reframing
    "K018": "method",         # 失败 More — failure budgeting
    "K019": "method",         # 想象 — mental sim, tactical
    "K022": "method",         # 感激 — gratitude practice
    "K032": "mental-model",   # 压力 — challenge/threat framework
    "K040": "method",         # 3P — Permission/Positive/Perspective
    "K041": "mental-model",   # 灵药 — myth-of-magic-pill
    "K042": "mental-model",   # 内向/外向 — recovery patterns
    "K061": "mental-model",   # 负面情绪 — RAIN framework
    "K073": "principle",      # 脆弱反脆弱 — antifragility law

    # ── 06-关系 ──
    "K043": "method",         # 创造优点 — daily virtue practice
    "K044": "method",         # 主动性 — networking tactical
    "K064": "principle",      # 场域 — field selection law
    "K066": "method",         # 共鸣 — empathy tactical
    "K075": "mental-model",   # 状态杠杆 — state leverage frame
    "K097": "method",         # 托付 — delegation tactical
    "K098": "mental-model",   # 地位 — status games frame
    "K099": "method",         # 礼 — etiquette tactical
    "K104": "mental-model",   # 替罪羊 — scapegoat mechanism
    "K105": "mental-model",   # 摩洛克 — Molech narrative
    "K106": "method",         # 第三物 — mediation tactical
    "K107": "principle",      # 剩余判断权 — residual discretion law
    "K108": "principle",      # 组织资本 — organizational capital law
    "K109": "principle",      # 人身依附 — governance law

    # ── 07-系统与策略 ──
    "K007": "method",         # 平均/顶尖 — selection tactical
    "K009": "principle",      # 指数 — compound law
    "K027": "method",         # 目标 — goal selection tactical
    "K033": "method",         # 少而精 — curation tactical
    "K037": "principle",      # 80/20 — Pareto law
    "K046B": "method",        # 场景 — context match
    "K049": "principle",      # 重尾 — fat-tail law
    "K050": "mental-model",   # 能动性 — agency concept
    "K051": "method",         # 限制能量 — energy mgmt tactical
    "K052": "principle",      # 不确定性 — Knightian law
    "K055": "mental-model",   # 供给侧 — supply-side frame
    "K056": "principle",      # 复利 — compound interest law
    "K063": "principle",      # 赛道 — track selection law
    "K065": "principle",      # 探索利用 — explore-exploit law
    "K071": "principle",      # 凯利公式 — Kelly law
    "K072": "principle",      # 非便利性 — inconvenience premium
    "K074": "principle",      # 期权 — options law
    "K089": "principle",      # 租 — rent economics
    "K090": "principle",      # 阿尔法 — alpha concept
    "K091": "principle",      # 杠杆 — leverage law
    "K092": "method",         # 窗口 — window mgmt tactical
    "K093": "method",         # 效果 — output vs outcome
    "K094": "principle",      # 沃德利地图 — Wardley Maps
    "K095": "principle",      # 成本病 — Baumol's disease
    "K096": "principle",      # 杰文斯悖论 — Jevons paradox
    "K100": "principle",      # 软预算 — soft budget constraint
    "K102": "principle",      # 激励相容 — incentive compatibility
    "K103": "principle",      # 柠檬市场 — lemons market

    # ── 08-意义与目的 ──
    "K001": "theme",          # 问题创造现实 — question-creation, identity
    "K002": "theme",          # No One Is Coming — self-responsibility, identity
    "K005": "mental-model",   # 接纳 — ACT framework
    "K012": "theme",          # 追求幸福 — happiness as theme
    "K013": "theme",          # Be the change — identity
    "K031": "theme",          # Calling
    "K039": "mental-model",   # 自我意识 — self-awareness frame
    "K101": "theme",          # 米提斯 — practice wisdom
    "K110": "theme",          # 死亡 — death contemplation
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify all 111 kids classified + show distribution")
    args = ap.parse_args()

    # Load all K-ids from KB
    kids = []
    for p in sorted(KB.glob("0?-*.json")):
        for e in json.load(p.open()):
            kids.append((e["id"], e["name"]))

    if args.check:
        missing = [k for k, _ in kids if k not in LAYER_OF]
        extra = [k for k in LAYER_OF if k not in {x[0] for x in kids}]
        print(f"分类状态: {len(kids)} 条目 / {len(LAYER_OF)} layer 映射")
        if missing:
            print(f"⚠ 缺失: {missing}")
        if extra:
            print(f"⚠ 多余: {extra}")
        if not missing and not extra:
            print(f"✓ 全 111 条都被分类")
        cnt = Counter(LAYER_OF[k] for k, _ in kids)
        total = sum(cnt.values())
        print(f"\n分布:")
        for layer in LAYERS:
            n = cnt.get(layer, 0)
            print(f"  {layer:<14} {n:>3}条  ({100*n/total:.0f}%)")
        return

    # Validate before writing
    missing = [k for k, _ in kids if k not in LAYER_OF]
    if missing:
        raise SystemExit(f"✗ 缺失 K-id: {missing}. 先添加分类.")

    cnt = Counter(LAYER_OF[k] for k, _ in kids)

    out = {
        "version": 1,
        "stats": {layer: cnt.get(layer, 0) for layer in LAYERS},
        "layer_of": LAYER_OF,
        "by_layer": {
            layer: sorted(kid for kid, l in LAYER_OF.items() if l == layer)
            for layer in LAYERS
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(KB.parent)} ({OUT.stat().st_size/1024:.1f} KB)")
    print(f"  method        {cnt['method']:>3}条")
    print(f"  mental-model  {cnt['mental-model']:>3}条")
    print(f"  principle     {cnt['principle']:>3}条")
    print(f"  theme         {cnt['theme']:>3}条")
    print(f"\nrun scripts/build_kb_index.py to surface layers in app/kb.py")


if __name__ == "__main__":
    main()

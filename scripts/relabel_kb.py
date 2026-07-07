#!/usr/bin/env python3
"""relabel_kb.py — relabel all 111 KB entries per diagnosis-taxonomy-v1.

Each entry gets `diagnosis_tags` replaced by:
  - 1–3 v1 taxonomy tags (from `Knowledge Base/diagnosis-taxonomy-v1.md`)
  - 0–2 free tags (preserved/refined from current tags)

Run:  python3 scripts/relabel_kb.py            # apply
       python3 scripts/relabel_kb.py --dry     # dry-run, show report only
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent / "Knowledge Base"
TAX = KB / "diagnosis-taxonomy-v1.md"

# ──────────────────────────────────────────────────────────────────────────
# v1 taxonomy (source of truth — keep in sync with diagnosis-taxonomy-v1.md)
# ──────────────────────────────────────────────────────────────────────────
V1_TAGS: set[str] = {
    # 1 · 心理感受
    "焦虑", "反刍", "低落", "疲惫", "空虚", "易怒",
    # 2 · 行为模式
    "拖延", "完美主义", "回避", "过度补偿", "边界模糊", "信息撑到饱和",
    # 3 · 思维模式
    "极端思维", "信念冲突", "证据失效", "视角固化",
    # 4 · 关系
    "关系摩擦", "被动等待",
    # 5 · 阶段与转折
    "平台期", "转型期", "身份迷茫",
    # 6 · 意义与系统
    "意义缺失", "死亡焦虑", "复利失灵", "赛道疑问",
}

# ──────────────────────────────────────────────────────────────────────────
# Mapping: K-id → (v1_taxonomy_tags, free_tags)
# Each entry: pick 1-3 v1 tags that the entry's CONTENT primarily serves when
# it's used as a tool/symptom-answer. Free tags = the original entry's
# identity (academic name + 1).
# ──────────────────────────────────────────────────────────────────────────
MAPPING: dict[str, tuple[list[str], list[str]]] = {
    # ── 01-身份 ──
    "K011": (["身份迷茫"],          ["脆弱性", "全人"]),
    "K014": (["信念冲突"],          ["限制性信念", "信念"]),
    "K015": (["身份迷茫"],          ["角色实验", "as-if"]),
    "K028": (["信念冲突"],          ["内在冲突", "整合"]),
    "K029": (["身份迷茫"],          ["人格分类工具"]),
    "K030": (["身份迷茫"],          ["自我发现", "工作取向"]),
    "K045": (["信念冲突"],          ["宿命论", "原生家庭"]),
    "K053": (["身份迷茫"],          ["角色vs内核", "自我结构"]),
    "K054": (["身份迷茫"],          ["路径依赖", "T型"]),
    "K062": (["身份迷茫"],          ["身份建构", "小步认同"]),
    # ── 02-认知 ──
    "K020": (["极端思维", "反刍"],  ["ABC", "CBT", "认知扭曲"]),
    "K046A": (["证据失效"],          ["概率思维", "分布"]),
    "K047": (["视角固化"],          ["提问", "元认知"]),
    "K048": (["视角固化"],          ["叙事", "建构主义"]),
    "K057": (["疲惫", "空虚"],       ["SDT", "内在动机"]),
    "K058": (["信念冲突"],          ["主动推理", "行动优先"]),
    "K067": (["证据失效"],          ["认知偏置", "决策陷阱"]),
    "K068": (["极端思维"],          ["分布", "中位vs平均"]),
    "K069": (["证据失效"],          ["概率更新", "贝叶斯"]),
    "K070": (["信息撑到饱和"],      ["调研止步", "决策驱动"]),
    "K076": (["证据失效"],          ["测量误差", "校准"]),
    "K077": (["证据失效"],          ["回归均值", "样本量"]),
    "K078": (["信念冲突"],          ["损失厌恶", "参考点"]),
    "K079": (["拖延"],              ["OODA", "决策循环"]),
    "K080": (["证据失效"],          ["预测", "Brier"]),
    # ── 03-学习 ──
    "K059": (["疲惫"],              ["认知负荷", "决策疲劳"]),
    "K081": (["信息撑到饱和"],      ["工作记忆", "教学设计"]),
    "K082": (["平台期"],            ["ICAP", "建构主义"]),
    "K083": (["平台期"],            ["刻意练习", "进阶"]),
    "K084": (["视角固化"],          ["心智模型", "图式"]),
    "K085": (["信息撑到饱和"],      ["跨学科", "迁移"]),
    "K086": (["信息撑到饱和"],      ["默会知识", "技能本体"]),
    "K087": (["平台期", "证据失效"], ["反馈循环", "教练"]),
    "K088": (["平台期"],            ["可取的困难", "学习阻力"]),
    # ── 04-行动 ──
    "K006": (["拖延"],              ["理想-行动", "三角定位"]),
    "K016": (["拖延"],              ["环境设计", "nudge"]),
    "K021": (["信息撑到饱和"],      ["Focus", "砍事"]),
    "K023": (["转型期"],            ["变革档位", "A/B/C"]),
    "K024": (["拖延"],              ["例行", "节奏"]),
    "K025": (["疲惫"],              ["恢复", "反脆弱"]),
    "K026": (["信息撑到饱和"],      ["外化思考", "笔记"]),
    "K034": (["边界模糊"],          ["拒绝", "默认拒绝"]),
    "K035": (["拖延"],              ["情绪回避", "执行困难"]),
    "K036": (["完美主义"],          ["标准过高", "怕评"]),
    "K038": (["疲惫"],              ["过程奖励", "自我决定"]),
    "K060": (["拖延"],              ["WOOP", "if-then"]),
    # ── 05-情绪 ──
    "K003": (["信念冲突"],          ["自尊", "过度防守"]),
    "K004": (["极端思维"],          ["消极偏向", "negativity"]),
    "K008": (["疲惫", "过度补偿"],   ["笑", "情绪调节"]),
    "K010": (["低落"],              ["Hedonic", "幸福基线"]),
    "K017": (["视角固化"],          ["P/N视角", "reframing"]),
    "K018": (["完美主义", "回避"],   ["失败预算", "failing-forward"]),
    "K019": (["焦虑", "反刍"],      ["mental simulation", "想象练习"]),
    "K022": (["低落"],              ["Gratitude", "积极心理学"]),
    "K032": (["焦虑"],              ["压力二元", "challenge/threat"]),
    "K040": (["低落"],              ["3P", "情绪调节"]),
    "K041": (["信息撑到饱和"],      ["灵药", "魔法思维"]),
    "K042": (["疲惫"],              ["能量管理", "社交耗竭"]),
    "K061": (["焦虑", "低落"],      ["RAIN", "接纳"]),
    "K073": (["易怒"],              ["反脆弱", "凸性"]),
    # ── 06-关系与社会 ──
    "K043": (["身份迷茫"],          ["美德实践", "自我建构"]),
    "K044": (["被动等待"],          ["Networking", "双向价值"]),
    "K064": (["转型期"],            ["场域选择", "环境"]),
    "K066": (["关系摩擦"],          ["共鸣", "镜像倾听"]),
    "K075": (["疲惫"],              ["状态杠杆", "放大器"]),
    "K097": (["边界模糊"],          ["托付", "授权"]),
    "K098": (["关系摩擦"],          ["地位博弈", "位序"]),
    "K099": (["关系摩擦"],          ["礼", "距离感"]),
    "K104": (["关系摩擦", "视角固化"], ["替罪羊", "群体心理"]),
    "K105": (["关系摩擦"],          ["Molech", "献祭叙事"]),
    "K106": (["关系摩擦"],          ["第三物", "调解"]),
    "K107": (["边界模糊"],          ["授权", "原则vs规则"]),
    "K108": (["转型期"],            ["组织资本", "无形资本"]),
    "K109": (["转型期"],            ["人身依附", "去人格化"]),
    # ── 07-系统与策略 ──
    "K007": (["赛道疑问"],          ["对标", "Reference group"]),
    "K009": (["复利失灵"],          ["复利", "非线性"]),
    "K027": (["赛道疑问"],          ["目标管理", "选择排序"]),
    "K033": (["信息撑到饱和"],      ["Curation", "上限"]),
    "K037": (["信息撑到饱和"],      ["Pareto", "杠杆"]),
    "K046B": (["转型期"],           ["场景判断", "Context"]),
    "K049": (["证据失效"],          ["重尾", "Fat tail"]),
    "K050": (["被动等待"],          ["Agency", "主权"]),
    "K051": (["疲惫"],              ["能量", "限制"]),
    "K052": (["焦虑"],              ["不确定性", "Knightian"]),
    "K055": (["赛道疑问"],          ["供给侧", "差异化"]),
    "K056": (["复利失灵"],          ["复利", "长半衰期"]),
    "K063": (["赛道疑问"],          ["赛道", "结构性"]),
    "K065": (["复利失灵"],          ["探索vs利用", "阶段"]),
    "K071": (["赛道疑问"],          ["Kelly", "仓位"]),
    "K072": (["赛道疑问"],          ["Inconvenience", "壁垒"]),
    "K074": (["赛道疑问"],          ["期权", "凸性"]),
    "K089": (["赛道疑问"],          ["Rent", "位置"]),
    "K090": (["赛道疑问"],          ["Alpha", "稀缺判断"]),
    "K091": (["复利失灵"],          ["杠杆", "四种杠杆"]),
    "K092": (["转型期"],            ["窗口期", "Window"]),
    "K093": (["复利失灵"],          ["Output vs Outcome", "有效产出"]),
    "K094": (["赛道疑问"],          ["Wardley Maps", "演化阶段"]),
    "K095": (["赛道疑问"],          ["Baumol", "成本病"]),
    "K096": (["信息撑到饱和"],      ["Jevons", "反弹效应"]),
    "K100": (["转型期"],            ["软预算", "制度约束"]),
    "K102": (["转型期"],            ["激励相容", "制度"]),
    "K103": (["证据失效"],          ["Lemons", "信号"]),
    # ── 08-意义与目的 ──
    "K001": (["视角固化"],          ["提问", "框架"]),
    "K002": (["被动等待"],          ["Agency", "主体性"]),
    "K005": (["信念冲突"],          ["ACT", "现实主义"]),
    "K012": (["空虚"],              ["Happiness", "过程取向"]),
    "K013": (["信念冲突"],          ["示范效应", "活出"]),
    "K031": (["意义缺失", "身份迷茫"], ["Calling", "使命"]),
    "K039": (["空虚"],              ["自我对话", "需求识别"]),
    "K101": (["信息撑到饱和"],      ["Metis", "实践智慧"]),
    "K110": (["死亡焦虑"],          ["Memento Mori", "有限性"]),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="only show coverage report, do not write")
    args = ap.parse_args()

    # Validate mapping against V1_TAGS
    unknown_v1 = sorted({t for _, (v1, _) in MAPPING.items() for t in v1} - V1_TAGS)
    if unknown_v1:
        raise SystemExit(f"✗ Mapping contains V1 tags not in taxonomy: {unknown_v1}")

    # Walk every JSON and rewrite diagnosis_tags
    json_paths = sorted(p for p in KB.glob("0?-*.json"))
    if not args.dry:
        for p in json_paths:
            entries = json.load(p.open(encoding="utf-8"))
            for e in entries:
                if e["id"] not in MAPPING:
                    print(f"  ⚠ {p.name}: {e['id']} ({e['name']}) has no mapping")
                    continue
                v1, free = MAPPING[e["id"]]
                e["diagnosis_tags"] = v1 + free
            with p.open("w", encoding="utf-8") as f:
                json.dump(entries, f, ensure_ascii=False, indent=2)
            print(f"  ✓ wrote {p.name}")

    # Coverage report
    print("")
    print("=" * 50)
    print("Coverage report")
    print("=" * 50)
    tag_entries: dict[str, list[str]] = {t: [] for t in sorted(V1_TAGS)}
    free_counter: Counter[str] = Counter()
    for p in json_paths:
        entries = json.load(p.open(encoding="utf-8"))
        for e in entries:
            for t in e.get("diagnosis_tags", []):
                if t in V1_TAGS:
                    tag_entries[t].append(e["id"])
                else:
                    free_counter[t] += 1

    print("\n[v1 taxonomy] tag → entries:")
    for t, ids in sorted(tag_entries.items(), key=lambda x: -len(x[1])):
        marker = "⚠" if not ids else " "
        print(f"  {marker} {t:<12} {len(ids):>2} 条   {', '.join(ids[:6])}{' …' if len(ids) > 6 else ''}")

    print(f"\n[free tags] top 20:")
    for t, c in free_counter.most_common(20):
        print(f"  {t:<14} {c}")

    # Sanity
    coverage = {t: len(ids) for t, ids in tag_entries.items()}
    unhit = [t for t, c in coverage.items() if c == 0]
    if unhit:
        print(f"\n⚠ V1 tags never matched (consider promoting to a free tag, or KB lacks coverage):")
        for t in unhit:
            print(f"    - {t}")


if __name__ == "__main__":
    main()

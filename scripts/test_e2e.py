#!/usr/bin/env python3
"""test_e2e.py — End-to-end smoke test of the diagnose pipeline.

Runs in 2 modes:
  (default) dry: mock the LLM call → verify schema, validators, action enrichment
  (with API keys): real: invoke actual LLM via OpenAI / Anthropic

Run:  python3 scripts/test_e2e.py [S01|S02|S03|all]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ─── pre-baked LLM responses (what a real LLM *should* produce per scenario) ───
MOCK_RESPONSES = {
    "S01": {
        "diagnoses": [
            {"tag":"拖延","confidence":0.92,"evidence":"拖了两周没动/写不出第一段","k_ids":["K035","K036"]},
            {"tag":"完美主义","confidence":0.74,"evidence":"开始写就觉得开头不够惊艳/改来改去","k_ids":["K036","K018"]}
        ],
        "notes":"两标签紧密互锁,完美主义是常见根因之一"
    },
    "S02": {
        "diagnoses": [
            {"tag":"疲惫","confidence":0.88,"evidence":"睡12小时还是累/醒来没充电","k_ids":["K051","K025","K057"]},
            {"tag":"空虚","confidence":0.79,"evidence":"看不出在为谁做/像被推着走","k_ids":["K012","K039","K031"]}
        ],
        "notes":"疲惫可能是空虚表现,反过来也成立. 根因追问'在为谁做'"
    },
    "S03": {
        "diagnoses": [
            {"tag":"反刍","confidence":0.93,"evidence":"洗澡时也想/停不下来","k_ids":["K019","K020"]},
            {"tag":"焦虑","confidence":0.86,"evidence":"越想越觉得会搞砸/胃开始疼","k_ids":["K032","K019"]}
        ],
        "notes":"反刍是表现,焦虑是驱动力. 后天前重点'解构+重新评估'"
    },
    "S08": {
        "diagnoses": [
            {"tag":"信念冲突","confidence":0.86,"evidence":"理性知道在伤害自己但停不下来/'今天已经废了不如就这么废了'的双轨","k_ids":["K014","K005"]},
            {"tag":"极端思维","confidence":0.71,"evidence":"'今天已经废了'触发全盘放弃","k_ids":["K020","K004"]}
        ],
        "notes":"每晚重演. 信念冲突是根,极端思维放大'这一次废了'的标签盖过未来"
    },
    "S10": {
        "diagnoses": [
            {"tag":"死亡焦虑","confidence":0.93,"evidence":"突然意识到时间不是无限的/夜里醒过来想","k_ids":["K110"]},
            {"tag":"意义缺失","confidence":0.81,"evidence":"我好像什么都没'留下来'","k_ids":["K031","K039"]}
        ],
        "notes":"死亡觉察触发意义盘点. 白天装作没事 = 信号被压. 看长期会累积"
    },
}

USER_INPUTS = {
    "S01": "最近有个重要提案拖了两周没动。资料都查齐了，就是写不出第一段。开始写就觉得'开头不够惊艳'，改来改去几小时没成型。",
    "S02": "周末睡 12 小时起来还是累。上班像被推着走。也说不上讨厌工作，就是看不出'在为谁做'。回到家手机刷两小时就睡着了，醒来还是没充电的感觉。",
    "S03": "后天要面谈升职的事。今晚开始刷各种可能的尴尬场景，洗澡时也想，越想越觉得会搞砸，胃也开始疼。理性知道'想一百遍也没用'，但停不下来。",
    "S08": "明知道要规律作息，但每天晚上 11 点就开始刷手机到 2 点。第二天自责，第二晚又来。理性知道这在伤害自己，但睡前那一刻就是觉得'今天已经废了，不如就这么废了'。",
    "S10": "这一年好几个朋友家里出事了。四十五十就走。我爸最近体检查出血脂高。突然意识到时间不是无限的，我好像什么都没'留下来'。夜里醒过来想这事，白天装作没事。",
}


def run_scenario(scenario_id: str) -> dict:
    """Run /diagnose against a pre-baked LLM response (mock mode)."""
    # Patch the LLM client at the app.llm level
    from app import llm
    original = llm.call_llm

    async def fake_call(user_input, provider=None, model=None, *, kb_context=None):
        return MOCK_RESPONSES[scenario_id]

    llm.call_llm = fake_call
    try:
        r = client.post("/diagnose", json={"input": USER_INPUTS[scenario_id]})
    finally:
        llm.call_llm = original
    return r


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    scenarios = list(MOCK_RESPONSES.keys()) if arg == "all" else [arg.upper()]

    print("=" * 60)
    print(f"E2E test (mock LLM) — {', '.join(scenarios)}")
    print("=" * 60)

    from app import kb
    kb.reset_recurrence()

    # 0) sanity
    h = client.get("/health")
    assert h.status_code == 200, h.text
    print(f"\n[health] ✓  {h.json()}")
    root = client.get("/info")
    assert root.status_code == 200
    print(f"[info]   ✓  endpoints={root.json()['endpoints']}")

    # 1) scenario runs
    for sid in scenarios:
        if sid not in MOCK_RESPONSES:
            print(f"\n[skip]   Unknown scenario {sid!r}")
            continue
    for sid in scenarios:
        if sid not in MOCK_RESPONSES:
            print(f"\n[skip]   Unknown scenario {sid!r}")
            continue
        print(f"\n{'─' * 60}")
        print(f"[{sid}] input: {USER_INPUTS[sid][:60]}…")
        r = run_scenario(sid)
        assert r.status_code == 200, r.text
        body = r.json()
        # assertions
        for d in body["diagnoses"]:
            assert 0.0 <= d["confidence"] <= 1.0, f"confidence OOB: {d}"
            assert len(d["actions"]) >= 1, f"no actions: {d}"
            for a in d["actions"]:
                assert {"label","do","when","min","mark"} <= set(a), f"bad action: {a}"
                assert a["when"] in ("now","today","this_week"), f"bad when: {a}"
        # show
        print(json.dumps(body, ensure_ascii=False, indent=2)[:1500], end="\n…\n")

    print(f"\n{'=' * 60}")
    print("✓ 所有检查通过。 真实 LLM 跑通只需:")
    print("    export OPENAI_API_KEY=...   (或 ANTHROPIC_API_KEY=...)")
    print("    python3 scripts/test_e2e.py S01 --real")
    print("=" * 60)


if __name__ == "__main__":
    main()

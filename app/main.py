"""Metis 诊断服务 — FastAPI app.

端点:
  GET  /         服务信息
  GET  /health   健康检查
  POST /diagnose 核心: 接受自然语言 → 输出 v1 标签 + K-id + 干预

启动:
  cd /Users/pengfit/.openclaw/workspace/metis
  python3 -m uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import os
from pathlib import Path

# Load .env if present (before any other imports that read env vars)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import llm
from . import kb
from . import store

app = FastAPI(
    title="Metis 诊断引擎",
    description="基于 25-标签 v1 Taxonomy + 111 条 KB 的症状诊断。",
    version="1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def ui():
    """Browser-based UI: Chinese form + 4 preset scenarios."""
    from fastapi.responses import FileResponse
    resp = FileResponse(
        Path(__file__).resolve().parent / "static" / "index.html",
        media_type="text/html; charset=utf-8",
    )
    # Avoid stale UI: always re-fetch on user reload
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


@app.get("/info")
async def root():
    return {
        "service": "metis-diagnose",
        "version": "1.0",
        "endpoints": ["/", "/health", "/diagnose", "/info"],
        "ui": "/  (browser frontend)",
        "v1_taxonomy_size": len(kb.v1_tags()),
        "embed_backend": "ollama:bge-m3" if kb._embedding_index() else "fallback:keyword-only",
    }


@app.get("/health")
async def health():
    emb_ok = kb._embedding_index() is not None
    return {
        "status": "ok",
        "service": "metis-diagnose",
        "v1_tags_loaded": len(kb.v1_tags()),
        "embed_ready": emb_ok,
        "embed_model": "bge-m3" if emb_ok else None,
    }


class ReflectionRequest(BaseModel):
    """Layer 5: 今日反思提交。"""

    entry_id: str = Field(..., description="诊断返回的 entry_id")
    did_it: bool = Field(..., description="今天唯一那 1 件, 做了吗?")
    feeling: str = Field("", description="过程感受 (选填)")
    learned: str = Field("", description="学到什么 / 下次不同 (选填)")


@app.post("/reflection")
async def reflection_endpoint(req: ReflectionRequest):
    """Layer 5: 提交今日反思。关联到某个诊断 entry。"""
    if not req.entry_id.strip():
        raise HTTPException(status_code=400, detail="entry_id 不能为空")
    ok = store.set_reflection(req.entry_id, {
        "did_it":  req.did_it,
        "feeling": req.feeling,
        "learned": req.learned,
    })
    if not ok:
        raise HTTPException(status_code=404, detail=f"entry_id={req.entry_id} 不存在")
    return {
        "status":   "recorded",
        "entry_id": req.entry_id,
        "when":     __import__("datetime").datetime.now().isoformat(),
    }


@app.get("/growth")
async def growth_endpoint(limit: int = 10):
    """Layer 6: 跨天累积视图。

    返回:
      - streak_days: 连续有 entry 的天数
      - total_entries: 总 entry 数
      - tag_frequency: tag 频次 (降序)
      - latest: 最近 N 条 entry 的精简摘要
    """
    entries = store.load_all()
    return {
        "streak_days":   store.streak_days(),
        "total_entries": len(entries),
        "tag_frequency": store.tag_frequency(),
        "latest": [
            {
                "entry_id":   e.get("entry_id"),
                "date":       e.get("date"),
                "created_at": e.get("created_at"),
                "tags":       [d.get("tag") for d in e.get("diagnoses", [])],
                "action":     e.get("action"),
                "has_reflection": bool(e.get("reflection")),
                "reflection": e.get("reflection"),
            }
            for e in entries[-limit:][::-1]  # 最新在前
        ],
    }


@app.post("/admin/reset")
async def admin_reset():
    """清运行时缓存: embedding index / Dify mode cache / recurrence tracker。
    下次 /diagnose 会重建 embedding (~18s 首次)。
    清 journal 不在范围 — 删除文件请直接操作 data/journal/。
    """
    from . import llm
    kb._embedding_index.cache_clear()
    llm._dify_mode_cache.clear()
    kb.reset_recurrence()
    return {
        "status": "reset",
        "cleared": ["embedding_index", "dify_mode_cache", "recurrence_tracker"],
        "note": "下次 /diagnose 会重建 embedding index (首调用 ~18s)",
    }


class DiagnoseRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=4000, description="用户的自然语言描述")
    provider: str | None = Field(None, description="openai 或 anthropic，覆盖环境默认")
    model: str | None = Field(None, description="覆盖环境默认的模型")


@app.post("/diagnose")
async def diagnose_endpoint(req: DiagnoseRequest):
    if not req.input.strip():
        raise HTTPException(status_code=400, detail="input 不能为空")

    # ── C 方案: KB 先检索，LLM 在候选里判断 ──
    # 让 KB 进"理解"那一刀: 给 LLM 一个受限的 K-id 候选集 + 摘要原文,
    # evidence 自然会引用 KB 短语, 不再是泛说。
    # v1.2: 用 hybrid (关键词 + embedding) 取代纯关键词检索。
    kb_hits = kb.search_hybrid(req.input, top_k=15)
    kb_context = kb.context_for_from_hits(kb_hits)

    try:
        raw = await llm.call_llm(
            req.input,
            provider=req.provider,
            model=req.model,
            kb_context=kb_context,
        )
    except llm.MissingAPIKeyError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"诊断失败: {e!s}")

    result = _validate(raw)
    tags = [d["tag"] for d in result["diagnoses"]]
    kb.record_tags(tags)

    # D 方案: 按当下时段过滤 actions
    from datetime import datetime
    hour = datetime.now().hour
    for d in result["diagnoses"]:
        d["actions"] = kb.time_sensitive_filter(d["actions"], hour=hour)

    result["next_layer"] = _build_next_layer(result["diagnoses"])
    # 让前端能看到 KB 检索命中了哪些 (debug + 透明度)
    result["kb_hits"] = [
        {"kid": kid, "score": round(score, 4)}
        for kid, score in kb_hits
    ]
    # ★ v1.3: 灵魂层 (5-layer) — 给用户看见诊断背后的知识 (Layer 3)
    # 聚合 LLM 选中的 K-id, 返回完整 KB 条目信息供 UI 解释"为什么"
    selected_kids: set[str] = set()
    for d in result["diagnoses"]:
        selected_kids.update(d.get("k_ids", []))
    hits_dict = {kid: score for kid, score in kb_hits}
    kb_index_dict = kb._index()["by_id"]
    refs: list[dict] = []
    for kid in sorted(selected_kids):
        e = kb_index_dict.get(kid)
        if not e:
            continue
        refs.append({
            "kid": kid,
            "name": e.get("name", ""),
            "summary": e.get("summary", ""),
            "diagnosis_tags": e.get("diagnosis_tags", []) or [],
            "score": round(hits_dict.get(kid, 0.0), 4),
        })
    result["kb_references"] = refs
    # 时间上下文, UI 可以用来展示"现在是哪段时间"
    result["time_context"] = kb.time_context(hour)

    # ★ v1.3 Layer 5: 落盘 + 返 entry_id 给前端用于反思提交
    chosen_action = None
    for d in result["diagnoses"]:
        acts = d.get("actions") or []
        if acts:
            chosen_action = acts[0].get("label")
            break

    entry_id = store.append_entry({
        "input":        req.input,
        "diagnoses":    result["diagnoses"],
        "kb_references": result["kb_references"],
        "kb_hits":      result["kb_hits"],
        "time_context": result["time_context"],
        "notes":        result["notes"],
        "next_layer":   result["next_layer"],
        "action":       chosen_action,
    })
    result["entry_id"] = entry_id
    return result


def _build_next_layer(diagnoses: list[dict]) -> dict:
    """如果同一个 v1 tag 在 7 天内被点亮 ≥ 3 次, 补上 principle/theme 层的 KB 入口。
    检索策略: 从本次诊断选中的 K-ids 出发, 走 KB 的 `related` 字段 2 层深度 (BFS),
    收集落在 principle/theme 层的 K-ids。
    """
    tags = [d["tag"] for d in diagnoses]
    if not tags:
        return {"triggered": False}

    hot_tag, hits = kb.max_recurrence(tags)
    if hits < 3 or not hot_tag:
        return {"triggered": False, "hot_tag": None, "count": hits}

    principle, theme = [], []
    seen: set[str] = set()
    queue: list[str] = []
    for d in diagnoses:
        for kid in d.get("k_ids", []):
            queue.append(kid)
            seen.add(kid)

    depth = 0
    while queue and depth < 3 and (len(principle) < 2 or len(theme) < 1):
        next_round = []
        for cur in queue:
            e = kb.entry(cur)
            if not e:
                continue
            for n in (e.get("related") or []):
                if n in seen or not kb.valid_kid(n):
                    continue
                seen.add(n)
                lay = kb.layer_of(n)
                if lay == "principle" and len(principle) < 2:
                    principle.append(n)
                elif lay == "theme" and len(theme) < 1:
                    theme.append(n)
                next_round.append(n)
        queue = next_round
        depth += 1

    return {
        "triggered":        True,
        "hot_tag":          hot_tag,
        "count":            hits,
        "window":           "7d",
        "principle_entries": [
            {"kid": kid, "name": kb.entry(kid).get("name", ""), "summary": kb.summary(kid)}
            for kid in principle
        ],
        "theme_entries": [
            {"kid": kid, "name": kb.entry(kid).get("name", ""), "summary": kb.summary(kid)}
            for kid in theme
        ],
        "hint": f"你 7 天内被点亮 '{hot_tag}' {hits} 次——这次看深一层: principle 与 theme。",
    }


def _validate(raw: dict) -> dict:
    """Strip hallucinations: tags outside v1, k-ids not in KB, malformed lists.
    Then enrich each diagnosis with REAL structured actions from KB.

    Handles both shapes:
      - wrapped:   {"result": {"diagnoses": [...], "notes": "..."}}
      - unwrapped: {"diagnoses": [...], "notes": "..."}
    Dify workflow / 一些 LLM 客户端会包一层 result / data / answer / output,
    校验前先 unwrap。
    """
    if not isinstance(raw, dict):
        return {"diagnoses": [], "notes": "LLM 输出非 dict", "fallback": ""}

    # Unwrap a single layer if a known wrapper key holds the schema.
    for wrapper in ("result", "data", "output", "answer"):
        inner = raw.get(wrapper)
        if isinstance(inner, dict) and (
            isinstance(inner.get("diagnoses"), list)
            or "notes" in inner
            or "fallback" in inner
        ):
            raw = inner
            break

    diagnoses_in = raw.get("diagnoses", [])
    if not isinstance(diagnoses_in, list):
        diagnoses_in = []

    valid_tags = kb.v1_tags()
    cleaned = []
    seen_tags: set[str] = set()
    for d in diagnoses_in:
        if not isinstance(d, dict):
            continue
        tag = d.get("tag", "")
        if not isinstance(tag, str) or tag not in valid_tags or tag in seen_tags:
            continue
        seen_tags.add(tag)

        k_ids = [k for k in (d.get("k_ids") or []) if isinstance(k, str) and kb.valid_kid(k)]
        evidence = d.get("evidence", "")
        if not isinstance(evidence, str):
            evidence = ""
        try:
            confidence = float(d.get("confidence", 0.5))
            confidence = round(max(0.0, min(1.0, confidence)), 2)
        except (TypeError, ValueError):
            confidence = 0.5

        # Pull REAL structured actions from KB (LLM does NOT pick actions)
        # ★ v1.3: 灵魂层 (5-layer) — 今天只做 1 件 (Layer 4)
        # max_n=1: 选一条最有力量的，让用户“能做”这一件
        actions = kb.top_actions_for(k_ids[:4], max_n=1)

        cleaned.append({
            "tag": tag,
            "confidence": confidence,
            "evidence": evidence.strip() or "(无原文引用)",
            "k_ids": k_ids[:4],
            "actions": actions,   # ← NEW: 实际动作从 KB 拉，不依赖 LLM
        })

    notes = raw.get("notes", "")
    fallback = raw.get("fallback", "")
    return {
        "diagnoses": cleaned,
        "notes": notes if isinstance(notes, str) else "",
        "fallback": fallback if isinstance(fallback, str) else "",
    }

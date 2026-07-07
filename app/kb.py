"""KB index loader & validators.

Single source for v1 taxonomy + K-id existence checks. Reused by /diagnose
to clean up hallucinated tags / k-ids from LLM output.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB_INDEX = HERE.parent / "Knowledge Base" / "_eval" / "kb-index.json"
LAYER_MAP = HERE.parent / "Knowledge Base" / "_eval" / "layer-mapping.json"

# Layer ordering: discovery order, used for next_layer surfacing.
LAYERS = ("method", "mental-model", "principle", "theme")

# In-memory recurrence tracker.
# lifetime: process. Re-seed on server restart (acceptable for MVP).
_recurrence: dict[str, list[datetime]] = defaultdict(list)


@lru_cache(maxsize=1)
def _index() -> dict:
    if not KB_INDEX.exists():
        raise FileNotFoundError(
            f"KB index not found at {KB_INDEX}. "
            "Run `python3 scripts/build_kb_index.py` first."
        )
    return json.loads(KB_INDEX.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _layer_map() -> dict:
    if not LAYER_MAP.exists():
        raise FileNotFoundError(
            f"Layer mapping not found at {LAYER_MAP}. "
            "Run `python3 scripts/tag_layers.py` first."
        )
    return json.loads(LAYER_MAP.read_text(encoding="utf-8"))


def v1_tags() -> set[str]:
    return set(_index()["v1_taxonomy"])


def valid_tag(tag: str) -> bool:
    return tag in v1_tags()


def valid_kid(kid: str) -> bool:
    return kid in _index()["by_id"]


def entry(kid: str) -> dict | None:
    return _index()["by_id"].get(kid)


def summary(kid: str) -> str:
    e = entry(kid)
    return e.get("summary", "") if e else ""


def actions_for(kid: str) -> list[dict]:
    """返回 KB 中该 K-id 的 structured actions（可能为空表）。"""
    e = entry(kid)
    if not e:
        return []
    iv = e.get("interventions")
    return iv if isinstance(iv, list) else []


def top_actions_for(kids: list[str], max_n: int = 3) -> list[dict]:
    """跨多个 K-id 拉动作，按优先级去重 + 截断：
    when='now' 优先, then when='today', then when='this_week'；
    同 when 内 min 升序；label 相同时保留第一条。
    """
    pool: list[dict] = []
    for kid in kids:
        pool.extend(actions_for(kid))
    when_rank = {"now": 0, "today": 1, "this_week": 2}
    pool.sort(key=lambda a: (when_rank.get(a.get("when", "today"), 9),
                              a.get("min", 60),
                              a.get("label", "")))
    seen: set[str] = set()
    out: list[dict] = []
    for a in pool:
        lab = a.get("label", "")
        if not lab or lab in seen:
            continue
        seen.add(lab)
        out.append(a)
        if len(out) >= max_n:
            break
    return out


# ────────────────────────────────────────────────────────────────────
# Time-aware action filtering (D 方案)
# 让“今日可执行”对当下真的敏感 — 深夜过滤耗能/社交类 action
# ────────────────────────────────────────────────────────────────────
_NIGHT_BLOCKED = {
    # 动作 label/do 里出现这些关键词, 深夜过滤掉
    "剧烈运动", "跑步", "出门", "散步", "联系", "打电话", "见面", "社交",
    "打肶", "购物", "厨房", "打扫", "做饭",
}

_NIGHT_HOUR_START = 22  # 22:00-06:00 为深夜
_NIGHT_HOUR_END = 6


def time_context(hour: int) -> dict:
    """根据小时返回时段上下文, UI 端用以提示。"""
    if hour >= _NIGHT_HOUR_START or hour < _NIGHT_HOUR_END:
        return {"mode": "night", "label": "深夜模式", "icon": "🌙", "hour": hour}
    if 6 <= hour < 9:
        return {"mode": "morning", "label": "早晨模式", "icon": "🌅", "hour": hour}
    if 9 <= hour < 12:
        return {"mode": "forenoon", "label": "上午", "icon": "☀️", "hour": hour}
    if 12 <= hour < 14:
        return {"mode": "noon", "label": "午间", "icon": "🍚", "hour": hour}
    if 14 <= hour < 18:
        return {"mode": "afternoon", "label": "下午", "icon": "☕", "hour": hour}
    return {"mode": "evening", "label": "傍晚", "icon": "🌆", "hour": hour}


def time_sensitive_filter(actions: list[dict], hour: int | None = None) -> list[dict]:
    """按当前时段过滤 actions。
    
    深夜 (22-6) 过滤耗能/社交类动作；
    其他时段原样返回。
    """
    from datetime import datetime
    if hour is None:
        hour = datetime.now().hour
    if not (_NIGHT_HOUR_START <= hour or hour < _NIGHT_HOUR_END):
        return actions

    def _is_night_blocked(a: dict) -> bool:
        text = (a.get("label", "") or "") + " " + (a.get("do", "") or "")
        return any(kw in text for kw in _NIGHT_BLOCKED)

    return [a for a in actions if not _is_night_blocked(a)]


def action_labels_for(kid: str) -> str:
    """用于在 prompt 里预览 K-id 能提供的动作标题列表。"""
    labels = [a.get("label", "") for a in actions_for(kid)]
    return " · ".join(filter(None, labels))


# ──────────────────────────────────────────────────────────────────────────
# Layer system (method / mental-model / principle / theme)
# ──────────────────────────────────────────────────────────────────────────
def layer_of(kid: str) -> str:
    """返回 K-id 的 layer ('method'|'mental-model'|'principle'|'theme')。找不到 = 'method' 兜底。"""
    return _layer_map()["layer_of"].get(kid, "method")


def k_ids_at_layer(layer: str, *, source_tags: list[str] | None = None, limit: int = 3) -> list[str]:
    """返回某 layer 里、且 diagnosis_tags 含 source_tags 任意一项的 K-id。"""
    by_id = _layer_map()["layer_of"]
    pool = []
    for kid, lay in by_id.items():
        if lay != layer:
            continue
        if not valid_kid(kid):
            continue
        if source_tags is not None:
            e = entry(kid)
            if not e:
                continue
            tags = set(e.get("diagnosis_tags", []) or [])
            if not (tags & set(source_tags)):
                continue
        pool.append(kid)
    return pool[:limit]


# ──────────────────────────────────────────────────────────────────────────
# Recurrence tracker (in-memory, 7-day window)
# ──────────────────────────────────────────────────────────────────────────
def record_tags(tags: list[str]) -> None:
    """记录今天触达的 tags (供下一次诊断参考)。"""
    now = datetime.now()
    for t in tags:
        _recurrence[t].append(now)


def recurrence_count(tag: str, within_days: int = 7) -> int:
    """该 tag 在过去 within_days 天内被点亮次数。"""
    cutoff = datetime.now() - timedelta(days=within_days)
    return sum(1 for t in _recurrence.get(tag, []) if t >= cutoff)


def max_recurrence(tags: list[str]) -> tuple[str | None, int]:
    """(最多的 tag, 次数)。无记录 → (None, 0)。"""
    best, best_n = None, 0
    for t in tags:
        n = recurrence_count(t)
        if n > best_n:
            best, best_n = t, n
    return best, best_n


def reset_recurrence() -> None:
    """测试/管理用。"""
    _recurrence.clear()


# ──────────────────────────────────────────────────────────────────────────
# Search (KB 进"理解"那一刀 — C 方案)
# ──────────────────────────────────────────────────────────────────────────
import math
from collections import Counter

# ── Embedding (via ollama bge-m3) ─────────────────────────────────────
# 111 条 KB 一次性 encode 进内存，~10s启动一次。
# ollama 不可用时，降级到纯关键词检索。
_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
_EMBED_MODEL = os.environ.get("METIS_EMBED_MODEL", "bge-m3")
_EMBED_DIM = 1024  # bge-m3 维度


def _ollama_embed(text: str) -> list[float]:
    """调 ollama /api/embeddings。返回 1024 维向量。"""
    import httpx
    r = httpx.post(
        f"{_OLLAMA_URL}/api/embeddings",
        json={"model": _EMBED_MODEL, "prompt": text},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    vec = data.get("embedding")
    if not isinstance(vec, list) or len(vec) != _EMBED_DIM:
        raise RuntimeError(
            f"ollama embedding 响应异常: dim={len(vec) if isinstance(vec, list) else 'N/A'} "
            f"model={_EMBED_MODEL}"
        )
    return vec


def _embedding_text(e: dict) -> str:
    """KB 条目 → embedding 输入文本。
    组合: name + summary + tags + interventions labels。
    加入动作 labels 可加强 K-id 的语义表达 (如 K032 里的'重新评估压力源')。
    """
    parts = [
        e.get("name", ""),
        e.get("summary", ""),
        " ".join(e.get("diagnosis_tags") or []),
    ]
    iv_labels = [
        a.get("label", "")
        for a in (e.get("interventions") or [])
        if a.get("label")
    ]
    if iv_labels:
        parts.append("动作: " + " · ".join(iv_labels))
    return "。".join(p for p in parts if p).strip()


@lru_cache(maxsize=1)
def _embedding_index() -> dict[str, list[float]] | None:
    """启动时一次性 embed 所有 KB 条目。ollama 不可用 → None, 降级。"""
    try:
        idx = _index()
        return {
            kid: _ollama_embed(_embedding_text(e))
            for kid, e in idx["by_id"].items()
        }
    except Exception as exc:  # noqa: BLE001
        # 降级: 纯关键词检索仍可用
        import warnings
        warnings.warn(
            f"[metis.kb] ollama embedding 不可用 ({type(exc).__name__}: {exc}), "
            f"降级到纯关键词检索",
            stacklevel=2,
        )
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    """cosine similarity。import numpy 在首次调用时, 避免冷启动开销。"""
    import numpy as np
    va, vb = np.array(a), np.array(b)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom < 1e-12:
        return 0.0
    return float(va @ vb / denom)


def embed_query(query: str) -> list[float] | None:
    """query embedding。ollama 不可用 → None。"""
    try:
        return _ollama_embed(query)
    except Exception:
        return None

# 中文通用词: 不参与检索语义，避免 '写下来' 撞 '停下来' 这类误召回
_STOPWORDS: set[str] = {
    "的", "了", "是", "我", "你", "他", "她", "它", "们", "自己",
    "在", "有", "和", "与", "或", "也", "都", "就", "还", "但", "而", "又",
    "会", "能", "要", "觉得", "可能", "好像", "应该", "不会", "得",
    "把", "被", "给", "从", "到", "向", "对", "为", "为了", "因为", "所以",
    "这", "那", "这个", "那个", "这些", "那些", "此", "彼",
    "什么", "怎么", "为什么", "哪", "里", "中",
    "一", "一下", "一直", "一起", "一样",
    "啊", "吧", "嗯", "哦", "哈", "唉", "呀", "呢", "吗",
    "今天", "明天", "后天", "昨天", "现在", "刚才", "以前", "以后",
    "不", "没", "没有", "别",
    "真的", "确实", "其实", "甚至", "就是", "不是",
    "再", "已经", "正在", "才", "便",
    "做", "说", "听", "感觉",
    # 上下/过来这类方向副词 + 高频动词: 在 name 子串命中里非常容易误伤
    "下来", "出来", "起来", "过来", "上去", "下去", "回来", "进来", "出去",
    "上来", "下来", "过来", "起来", "过去",
    "想", "看", "想看", "认为", "觉得", "感觉", "感到", "发现",
}


def _tokenize(s: str, *, drop_stopwords: bool = True) -> set[str]:
    """中文友好分词: 去标点 + 词 + 2/3-gram, 可选去停用词。
    返回 set, 用于集合交集比较。
    """
    if not s:
        return set()
    cleaned = re.sub(r"[，。！？、；：\s《》（）()\[\]【】\"'`´]+", " ", s.lower())
    out: set[str] = set()
    for w in cleaned.split():
        if w:
            out.add(w)
    flat = re.sub(r"\s+", "", cleaned)
    for n in (2, 3):
        for i in range(len(flat) - n + 1):
            out.add(flat[i:i + n])
    if drop_stopwords:
        out = out - _STOPWORDS
    return out


def _contains_stopword(sub: str) -> bool:
    """substring 里是否含任何停用词 (按整词边界判断)。
    例如 '停下来' 含 '下来', 含 '想' → True, 跳过 name 命中。
    """
    for sw in _STOPWORDS:
        if sw in sub:
            return True
    return False


def search(query: str, top_k: int = 15) -> list[tuple[str, float]]:
    """召回优先的检索。返回 [(kid, score)] 按相关度降序。

    设计取舍:
      - 不上 IDF (症状描述词会被 IDF 误压低)
      - name 严格 substring 命中 (高 precision, 去停用词避免 '下来' 误伤)
      - summary 任何 2+ 字子串命中 (高 recall, 允许噪声)
      - diagnosis_tags 文字命中 (高 precision)
      - LLM 看 top_k=15 候选, 自己挑 → KB context 不是束缚, 是参考

    评分 (可叠加):
      +5.0  query 子串命中 name (2-4 字, 子串内不含 stopword)
      +4.0  query 命中任一 diagnosis_tags (每命中 +2.0)
      +2.0  query 任一 2-4 字子串命中 summary (每命中 +2.0, 最多 +6.0)
      +1.5  query 命中任一 interventions[].label
      +0.3  query ∩ summary 词重叠 (去停用词后, 每重叠词 +0.3)

    Returns:
        list of (kid, score), len <= top_k, score > 0
    """
    idx = _index()
    by_id = idx["by_id"]

    q_clean = query.strip()
    if not q_clean:
        return []

    # 预生成 query 子串 (2-4 字, 去停用词)
    q_subs: list[str] = []
    for n in (2, 3, 4):
        for i in range(len(q_clean) - n + 1):
            sub = q_clean[i:i + n]
            if _contains_stopword(sub):
                continue
            q_subs.append(sub)

    q_tokens = _tokenize(q_clean)

    scored: list[tuple[str, float]] = []
    for kid, e in by_id.items():
        score = 0.0

        # 1. name 严格 substring 命中
        name_text = e.get("name") or ""
        if name_text:
            for sub in q_subs:
                if sub in name_text:
                    score += 5.0
                    break

        # 2. diagnosis_tags 文字
        tags = e.get("diagnosis_tags") or []
        tag_hits = [t for t in tags if t and t in q_clean]
        if tag_hits:
            score += 4.0 + 2.0 * len(tag_hits)

        # 3. summary 子串命中 (高 recall)
        summary_text = e.get("summary") or ""
        if summary_text:
            sub_hits = 0
            seen: set[str] = set()
            for sub in q_subs:
                if sub in seen:
                    continue
                if sub in summary_text:
                    sub_hits += 1
                    seen.add(sub)
            if sub_hits:
                score += min(2.0 + 2.0 * sub_hits, 6.0)

        # 4. action label 命中
        labels = [a.get("label", "") for a in (e.get("interventions") or [])]
        for lab in labels:
            if lab and any(sub in lab for sub in q_subs if len(sub) >= 2):
                score += 1.5
                break

        # 5. summary 词重叠 (去停用词)
        s_toks = _tokenize(summary_text)
        overlap = q_tokens & s_toks
        if overlap:
            score += 0.3 * len(overlap)

        if score > 0:
            scored.append((kid, round(score, 3)))

    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored[:top_k]


def search_hybrid(query: str, top_k: int = 25, *, alpha: float = 0.5) -> list[tuple[str, float]]:
    """关键词 + embedding cosine 融合检索。返回 [(kid, score)] 按相关度降序。

    alpha: embedding 权重 (0-1)
      0.5  默认 — 平衡, 给 LLM 充足候选 (推荐)
      0.6  偏 embedding (召回语义相关条目)
      1.0  纯 embedding
      0.0  纯关键词 (调用 search())

    降级: ollama embedding 不可用 → 纯关键词检索。

    Returns:
        list of (kid, fused_score), len <= top_k
    """
    # 1. 关键词召回 (放 大召回 到 2×top_k)
    kw_hits = search(query, top_k=max(top_k * 2, 20))
    kw_dict: dict[str, float] = {kid: s for kid, s in kw_hits}

    # 2. embedding cosine 召回
    emb_index = _embedding_index()
    if emb_index is None:
        # ollama 不可用, 纯关键词结果直接返回
        return kw_hits[:top_k]

    q_vec = embed_query(query)
    if q_vec is None:
        return kw_hits[:top_k]

    emb_scores: dict[str, float] = {
        kid: _cosine(q_vec, vec) for kid, vec in emb_index.items()
    }

    # 3. 融合: min-max 归一化两边, 加权求和
    max_kw = max(kw_dict.values(), default=0.0) or 1.0
    max_emb = max(emb_scores.values(), default=0.0) or 1.0

    all_kids = set(kw_dict) | set(emb_scores)
    fused: list[tuple[str, float]] = []
    for kid in all_kids:
        kw_norm = kw_dict.get(kid, 0.0) / max_kw
        emb_norm = emb_scores.get(kid, 0.0) / max_emb
        score = alpha * emb_norm + (1.0 - alpha) * kw_norm
        fused.append((kid, round(score, 4)))

    fused.sort(key=lambda x: (-x[1], x[0]))
    return [(kid, s) for kid, s in fused[:top_k] if s > 0]


def context_for(query: str, top_k: int = 8) -> str:
    """把检索到的 K-id 拼成 LLM 友好的 KB 上下文。

    设计目的:
      - 让 LLM 在受限候选集里判断 (避免在 25 个 tag × 111 个 K-id 盲选)
      - evidence 引导 LLM 引用下方【摘要】短语 (而非泛说)
      - 给 LLM 看 action label 预览, 让诊断与处方方向自洽
    """
    hits = search(query, top_k)
    return context_for_from_hits(hits)


def context_for_from_hits(hits: list[tuple[str, float]]) -> str:
    """根据预先算出的 hits 渲染 KB context 块。避免重复跑 search。"""
    if not hits:
        return "（KB 未命中候选 — 描述太模糊, 建议用户补充情境）"

    lines = ["<<KB_CONTEXT>>"]
    lines.append("以下是从知识库检索出的最相关条目。请在候选 tag + k_ids 中判断。")
    lines.append("evidence 必须引用下方【摘要】或【动作预览】中的具体短语，不要泛说。")
    lines.append("")
    for kid, score in hits:
        e = entry(kid)
        if not e:
            continue
        name = e.get("name", "")
        summary = e.get("summary", "")
        tags = e.get("diagnosis_tags") or []
        tag_str = " / ".join(tags) if tags else "—"
        actions_lab = action_labels_for(kid)
        lines.append(f"- [{kid}] {name} | tag候选: {tag_str} | 相关度: {score:.3f}")
        lines.append(f"  【摘要】{summary}")
        if actions_lab:
            lines.append(f"  【动作预览】{actions_lab}")
        lines.append("")
    lines.append("<</KB_CONTEXT>>")
    return "\n".join(lines)

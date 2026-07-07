"""Journal store — Layer 5 (Reflection) + Layer 6 (Growth) 的数据层。

每天一个文件: data/journal/YYYY-MM-DD.json
每天可能多条 entry (用户可能一天诊断多次)。
每条 entry 自带 entry_id (8 位 uuid) + date + created_at, 便于后续 /reflection 定位。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "journal"


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _date_file(d: date) -> Path:
    return DATA_DIR / f"{d.isoformat()}.json"


def _load(d: date) -> list[dict]:
    f = _date_file(d)
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _save(d: date, entries: list[dict]) -> None:
    _ensure_dir()
    _date_file(d).write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ──────────────────────────────────────────────────────────────────────
# Write
# ──────────────────────────────────────────────────────────────────────
def append_entry(entry: dict) -> str:
    """追加一条诊断 entry 到今天的 journal。返回 entry_id。

    自动补:
      - entry_id  (8 位 uuid 短码)
      - date       (今天, ISO)
      - created_at (datetime.now().isoformat())
    """
    entry_id = entry.get("entry_id") or str(uuid4())[:8]
    entry["entry_id"] = entry_id
    entry["date"] = date.today().isoformat()
    entry.setdefault("created_at", datetime.now().isoformat())
    _save(date.today(), _load(date.today()) + [entry])
    return entry_id


def set_reflection(entry_id: str, reflection: dict) -> bool:
    """更新一条 entry 的 reflection。跨天查找 (entry 可能在前几天写入)。"""
    if not DATA_DIR.exists():
        return False
    for f in DATA_DIR.glob("*.json"):
        d = date.fromisoformat(f.stem)
        entries = _load(d)
        for e in entries:
            if e.get("entry_id") == entry_id:
                e["reflection"] = reflection
                e["reflection_at"] = datetime.now().isoformat()
                _save(d, entries)
                return True
    return False


# ──────────────────────────────────────────────────────────────────────
# Read
# ──────────────────────────────────────────────────────────────────────
def load_all() -> list[dict]:
    """所有 entry 平铺返回 (按 entry 的 created_at 排序)。"""
    if not DATA_DIR.exists():
        return []
    out: list[dict] = []
    for f in sorted(DATA_DIR.glob("*.json")):
        out.extend(_load(date.fromisoformat(f.stem)))
    out.sort(key=lambda e: e.get("created_at", ""))
    return out


def streak_days(today: date | None = None) -> int:
    """连续多少天有 journal entry。断一天即清零。"""
    if today is None:
        today = date.today()
    if not DATA_DIR.exists():
        return 0
    n = 0
    cursor = today
    while (DATA_DIR / f"{cursor.isoformat()}.json").exists():
        n += 1
        cursor = cursor.replace()  # date not hashable, but okay...
        from datetime import timedelta
        cursor = cursor - timedelta(days=1)
    return n


def tag_frequency() -> dict[str, int]:
    """所有 entry 的 tag 频次。用于 Growth 趋势。"""
    out: dict[str, int] = {}
    for e in load_all():
        for d in e.get("diagnoses", []):
            t = d.get("tag")
            if t:
                out[t] = out.get(t, 0) + 1
    return dict(sorted(out.items(), key=lambda x: -x[1]))

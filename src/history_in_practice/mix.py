"""Editorial mix and the persisted plan (owner decision 2026-10-31, docs/ADDENDUM_READER_FEEDBACK_20261031.md §三–四).

Replaces the equal four-slot rotation [china_ancient, world, china_modern, us]. Per 7 editions: about 4 China stories
(ancient and modern together) and about 3 from elsewhere (world: Europe, other Asia, ...; us). It is a soft target:

* Pattern position k (counted over all editions ever scheduled) wants PATTERN[k % 7] (default C O C O C O C).
* Within the wanted group: China alternates ancient/modern when both are available; any pick prefers no shared theme
  tags and a different region than the previous pick; then the oldest admitted edition. Deterministic, no randomness.
* If the wanted group has nothing eligible, the other group may stand in only while every trailing window of 7 keeps
  China between MIN_CHINA and MAX_CHINA; otherwise the plan stops there (that is the coverage).
* Only editions admitted *now* are planned (final_edit.current_eligibility via the caller's pool).

The plan is persisted by position (table edition_plan). Scheduling takes the planned edition for the next position if
it is still eligible; otherwise it re-plans from that position and records why. Retries and resumes reuse the stored
plan instead of picking again. Coverage = scheduled ahead + the length of the plan the eligible inventory can fill.
"""
from __future__ import annotations
import json, time
from pathlib import Path
from .config import REPO, load_project

GROUP = {"china_ancient": "china", "china_modern": "china", "world": "other", "us": "other"}
_M = load_project().get("mix", {})
PATTERN = _M.get("pattern", ["china", "other", "china", "other", "china", "other", "china"])
MIN_CHINA, MAX_CHINA = _M.get("min_china_per_7", 3), _M.get("max_china_per_7", 5)
REGIONS = REPO / "config" / "regions.json"
SCHEMA = """CREATE TABLE IF NOT EXISTS edition_plan(position INTEGER PRIMARY KEY, edition_id TEXT NOT NULL, grp TEXT, reason TEXT,
            planned_at REAL, status TEXT NOT NULL DEFAULT 'planned');"""


def region(o: dict | None, eid: str, category: str) -> str:
    if o and o.get("region"):
        return o["region"]
    if category in ("china_ancient", "china_modern"):
        return "中国"
    if category == "us":
        return "美国"
    m = json.loads(REGIONS.read_text(encoding="utf-8")) if REGIONS.exists() else {}
    return m.get(eid, "其他地区")


def tags_of(eid: str, o: dict | None) -> list[str]:
    if o and o.get("tags"):
        return list(o["tags"])
    global _TAGS
    if _TAGS is None:
        _TAGS = {}
        for p in (REPO / "config" / "candidates").glob("*.json"):
            c = json.loads(p.read_text(encoding="utf-8"))
            if c.get("tags"):
                _TAGS[c["candidate_id"]] = c["tags"]
        f = REPO / "config" / "edition_tags.json"
        if f.exists():
            _TAGS.update({k: v for k, v in json.loads(f.read_text(encoding="utf-8")).items() if not k.startswith("_")})
    return list(_TAGS.get(eid, []))


_TAGS = None


def item(eid, category, o=None, admitted_at=0.0) -> dict:
    tags = tags_of(eid, o)
    return {"edition_id": eid, "category": category, "group": GROUP.get(category, "other"), "region": region(o, eid, category),
            "tags": list(tags), "title": ((o or {}).get("title") or {}).get("zh", eid), "admitted_at": admitted_at}


def plan(pool: list[dict], days: int, start: int, history: list[dict] | None = None) -> list[dict]:
    """Deterministic greedy plan over `pool` (items, any order) for positions start..start+days-1."""
    left = sorted(pool, key=lambda x: (x["admitted_at"], x["edition_id"]))
    seq = list(history or [])[-6:]; out = []
    for k in range(days):
        want = PATTERN[(start + k) % len(PATTERN)]
        prev = (seq + out)[-1] if seq + out else None
        last_of = lambda g: next((x for x in reversed(seq + out) if x["group"] == g), None)
        last_china = last_of("china")

        def best(group):
            c = [x for x in left if x["group"] == group]
            if not c:
                return None, ""
            def score(x):
                s = 0
                if group == "china" and last_china and x["category"] != last_china["category"]:
                    s -= 4                                   # alternate ancient / modern
                if prev and not set(x["tags"]) & set(prev["tags"]):
                    s -= 2                                   # vary the theme
                if prev and x["region"] != prev["region"]:
                    s -= 1                                   # vary the place
                same = last_of(group)
                if group == "other" and same and x["region"] != same["region"]:
                    s -= 1                                   # and between consecutive "elsewhere" stories
                return s
            x = min(c, key=lambda x: (score(x), x["admitted_at"], x["edition_id"]))
            why = [f"{'中国' if group == 'china' else '其他地区'}位（模式第 {(start + k) % len(PATTERN) + 1} 位）"]
            if group == "china" and last_china and x["category"] != last_china["category"]:
                why.append("古今交替")
            if prev and not set(x["tags"]) & set(prev["tags"]):
                why.append("主题与上一篇不同")
            if prev and x["region"] != prev["region"]:
                why.append("地区变化")
            why.append("在合格库存中入库最早")
            return x, "；".join(why)
        x, why = best(want)
        if x is None:
            alt = "other" if want == "china" else "china"
            x, why = best(alt)
            if x is None:
                break
            window = (seq + out + [x])[-7:]
            n = sum(1 for y in window if y["group"] == "china")
            if n > MAX_CHINA or len(window) - n > 7 - MIN_CHINA:
                break                                        # substituting would break the 4/3 band in a window of 7: stop (coverage ends)
            why = f"替补：{'中国' if want == 'china' else '其他地区'}位暂无合格稿；" + why
        left.remove(x); out.append(dict(x, position=start + k, reason=why))
    return out


def init(db):
    db.executescript(SCHEMA)


def stored(db, start: int) -> list[dict]:
    init(db)
    return [dict(zip(("position", "edition_id", "group", "reason", "planned_at", "status"), r)) for r in
            db.execute("SELECT position, edition_id, grp, reason, planned_at, status FROM edition_plan WHERE position>=? ORDER BY position", (start,))]


def persist(db, start: int, items: list[dict], why: str):
    """Replace the planned (not yet used) positions from `start` on with `items`."""
    init(db)
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute("DELETE FROM edition_plan WHERE position>=? AND status='planned'", (start,))
        for x in items:
            db.execute("INSERT OR REPLACE INTO edition_plan(position, edition_id, grp, reason, planned_at, status) VALUES(?,?,?,?,?, 'planned')",
                       (x["position"], x["edition_id"], x["group"], f"{x['reason']}（{why}）", time.time()))
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK"); raise


def mark_used(db, position: int, eid: str):
    init(db)
    db.execute("INSERT OR REPLACE INTO edition_plan(position, edition_id, grp, reason, planned_at, status) VALUES(?,?,"
               "COALESCE((SELECT grp FROM edition_plan WHERE position=?), ''), COALESCE((SELECT reason FROM edition_plan WHERE position=?), ''),"
               "COALESCE((SELECT planned_at FROM edition_plan WHERE position=?), ?), 'used')", (position, eid, position, position, position, time.time()))


def needs(days: int, start: int) -> dict:
    """How many of each category `days` planned positions want (China split ancient/modern, other split world 2 : us 1)."""
    china = sum(1 for k in range(days) if PATTERN[(start + k) % len(PATTERN)] == "china"); other = days - china
    return {"china_ancient": (china + 1) // 2, "china_modern": china // 2, "world": other - other // 3, "us": other // 3}

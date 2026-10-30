"""Episode registry and duplicate detection (PLAN §4.4).

An *episode* is one concrete story (a specific decision, inquiry, recall...).
IDs are immutable, sequential, and carry no dedup meaning. Dedup signals:
1. same canonical event QID (after redirect)            -> duplicate
2. overlapping canonical source span + a shared person  -> duplicate
3. same people/place/time and a similar action          -> review (pending)
4. otherwise                                            -> distinct
Spans are (work_ref, start, end) offsets in the ONE configured edition of each
work (the adapter ref, e.g. "zh:史記/卷056"); translations must be mapped to the
original work's ref before they can be compared.
All active statuses (reserved/prepared/scheduled/published) are checked, and a
unique index on the core span blocks racing reservations.
"""
from __future__ import annotations
import json, re, sqlite3, time
from pathlib import Path
from .textnorm import t2s

ACTIVE = ("reserved", "prepared", "checked", "scheduled", "published")
SCHEMA = """
CREATE TABLE IF NOT EXISTS episode(
  episode_id TEXT PRIMARY KEY, status TEXT NOT NULL, title TEXT, category TEXT,
  parent_event TEXT, event_qid TEXT, persons TEXT, year_from INT, year_to INT,
  place TEXT, action TEXT, core_span TEXT NOT NULL, spans TEXT NOT NULL,
  search_text TEXT, bigrams TEXT, created_at REAL);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_core_span ON episode(core_span)
  WHERE status IN ('reserved','prepared','checked','scheduled','published');
CREATE TABLE IF NOT EXISTS alias(alias TEXT PRIMARY KEY, entity TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS qid_redirect(old TEXT PRIMARY KEY, new TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS episode_seq(n INTEGER);
CREATE VIRTUAL TABLE IF NOT EXISTS episode_fts USING fts5(episode_id UNINDEXED, bigrams);
"""


def norm(s: str) -> str:
    return t2s((s or "").strip()).lower()


def bigrams(s: str) -> str:
    s = t2s(s or ""); out = []
    for run in re.findall(r"[一-鿿]+", s):
        out += [run[i:i + 2] for i in range(len(run) - 1)] or [run]
    return " ".join(out + re.findall(r"[a-z0-9]+", s.lower()))


def init(db: sqlite3.Connection, aliases: dict | None = None, redirects: dict | None = None):
    db.executescript(SCHEMA)
    for a, e in (aliases or {}).items():
        db.execute("INSERT OR IGNORE INTO alias VALUES(?,?)", (norm(a), e))
    for o, n in (redirects or {}).items():
        db.execute("INSERT OR REPLACE INTO qid_redirect VALUES(?,?)", (o, n))


def entity(db, name):
    r = db.execute("SELECT entity FROM alias WHERE alias=?", (norm(name),)).fetchone()
    return r[0] if r else "name:" + norm(name)


def canon_qid(db, q):
    seen = set()
    while q and q not in seen:
        seen.add(q); r = db.execute("SELECT new FROM qid_redirect WHERE old=?", (q,)).fetchone()
        if not r: break
        q = r[0]
    return q


def _overlap(a, b):
    return any(x[0] == y[0] and x[1] < y[2] and y[1] < x[2] for x in a for y in b)


def _sim(a, b):
    A, B = set(bigrams(a).split()), set(bigrams(b).split())
    return len(A & B) / max(1, len(A | B))


def check(db, ep: dict) -> tuple[str, str]:
    """ep: {persons, year_from, year_to, place, action, spans:[[ref,start,end]], event_qid?, title?}"""
    ps = {entity(db, p) for p in ep["persons"]}; sp = [tuple(x) for x in ep["spans"]]
    q = canon_qid(db, ep.get("event_qid")); verdict = ("distinct", "")
    cols = [d[0] for d in db.execute("SELECT * FROM episode LIMIT 0").description]
    for row in db.execute(f"SELECT * FROM episode WHERE status IN {ACTIVE}"):
        r = dict(zip(cols, row)); rps = set(json.loads(r["persons"])); rsp = [tuple(x) for x in json.loads(r["spans"])]
        if q and r["event_qid"] and q == canon_qid(db, r["event_qid"]):
            return "duplicate", f"same event QID as {r['episode_id']}"
        if _overlap(sp, rsp) and ps & rps:
            return "duplicate", f"same source passage and person as {r['episode_id']} ({r['status']})"
        same = ps & rps and norm(ep["place"]) == r["place"] and not (ep["year_to"] < r["year_from"] or r["year_to"] < ep["year_from"])
        if same and _sim(ep["action"], r["action"]) >= 0.35:
            verdict = ("review", f"same people/place/time and similar action as {r['episode_id']}")
    return verdict


def reserve(db, ep: dict, status="reserved") -> tuple[str | None, tuple[str, str]]:
    db.execute("BEGIN IMMEDIATE")
    try:
        v = check(db, ep)
        if v[0] != "distinct":
            db.execute("ROLLBACK"); return None, v
        n = db.execute("SELECT COALESCE(MAX(n),0)+1 FROM episode_seq").fetchone()[0]
        db.execute("INSERT INTO episode_seq VALUES(?)", (n,))
        eid = ep.get("episode_id") or f"ep-{n:06d}"
        core = ep["spans"][0]; core_key = f"{core[0]}@{core[1]}"
        text = " ".join([ep.get("title", ""), ep.get("action", ""), " ".join(ep["persons"]), ep["place"]])
        db.execute("INSERT INTO episode VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            eid, status, ep.get("title"), ep.get("category"), ep.get("parent_event"), canon_qid(db, ep.get("event_qid")),
            json.dumps(sorted({entity(db, p) for p in ep["persons"]})), ep["year_from"], ep["year_to"], norm(ep["place"]),
            norm(ep["action"]), core_key, json.dumps(ep["spans"]), t2s(text), bigrams(text), time.time()))
        db.execute("INSERT INTO episode_fts VALUES(?,?)", (eid, bigrams(text)))
        db.execute("COMMIT"); return eid, v
    except sqlite3.IntegrityError as e:
        db.execute("ROLLBACK"); return None, ("duplicate", f"reservation constraint: {e}")


def set_status(db, episode_id, status):
    db.execute("UPDATE episode SET status=? WHERE episode_id=?", (status, episode_id))


def recall(db, text: str, limit=10) -> list[str]:
    """Candidate recall for a free-text query (CJK bigram FTS + substring)."""
    q = " OR ".join(f'"{b}"' for b in set(bigrams(text).split())) or '""'
    a = [r[0] for r in db.execute("SELECT episode_id FROM episode_fts WHERE episode_fts MATCH ? LIMIT ?", (q, limit))]
    b = [r[0] for r in db.execute("SELECT episode_id FROM episode WHERE instr(search_text, ?) > 0 LIMIT ?", (t2s(text), limit))]
    return list(dict.fromkeys(a + b))


def rebuild_from_content(db, content_paths: list[Path]) -> int:
    """Rebuild active episodes from committed content objects (SQLite loss recovery)."""
    n = 0
    for p in content_paths:
        o = json.loads(Path(p).read_text(encoding="utf-8"))
        ep = o.get("episode")
        if not ep:
            continue
        status = "published" if o.get("status") == "published" else ("checked" if o.get("status") in ("checked", "sample") else "prepared")
        eid, v = reserve(db, dict(ep, episode_id=o["episode_id"], title=o["title"]["zh"], category=o["category"]), status=status)
        n += 1 if eid else 0
    return n

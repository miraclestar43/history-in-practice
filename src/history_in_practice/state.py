"""SQLite state: editions, transitions, site publications, per-recipient deliveries.

Rules that matter (tested in tests/test_state_mail.py):
* Edition status only moves along ALLOWED; content is frozen once `checked`
  (content_sha256 recorded) and a changed hash requires a new revision.
* Deliveries are per (edition, revision, recipient_key). recipient_key is a
  salted SHA-256 of the address; the address itself is never stored.
* `recover()` after a crash turns `sending` into `unknown`. `unknown` is never
  retried automatically: SMTP may already have accepted the message.
* The expected recipient set is frozen (salted keys) when an edition enters
  `email_pending`; it is complete only when every frozen key is `accepted`.
* An in-flight edition whose date has passed becomes `overdue` (terminal,
  alerted): stale email is never sent automatically on a later day.
* `approval` records why a `checked` edition may be scheduled (editor record,
  pipeline gates, named exception, approved sample); `origin` is pipeline/sample.
"""
from __future__ import annotations
import hashlib, json, sqlite3, time
from pathlib import Path

ALLOWED = {
    None: {"prepared", "pending_review", "rejected"},
    "pending_review": {"prepared", "rejected"},
    "prepared": {"checked", "pending_review", "rejected"},
    "checked": {"scheduled", "archived", "pending_review", "rejected"},
    "scheduled": {"archived", "checked", "overdue"},
    "archived": {"site_committed", "overdue"},
    "site_committed": {"site_live", "site_committed", "overdue"},
    "site_live": {"email_pending", "overdue"},
    "email_pending": {"complete", "email_pending", "overdue"},
    "complete": set(), "rejected": set(), "overdue": set(),
}
DELIVERY_FINAL = {"accepted"}
# A `checked` edition may be scheduled only with a recorded approval; samples additionally need an explicit sample approval.
SCHEDULABLE_SQL = "(COALESCE(approval,'') != '' AND (COALESCE(origin,'pipeline') != 'sample' OR approval LIKE 'sample-approved%'))"

SCHEMA = """
CREATE TABLE IF NOT EXISTS edition(
  edition_id TEXT PRIMARY KEY, episode_id TEXT, category TEXT, edition_date TEXT,
  revision INTEGER NOT NULL DEFAULT 1, content_sha256 TEXT, path TEXT,
  status TEXT NOT NULL, reason TEXT, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS transition(
  id INTEGER PRIMARY KEY, edition_id TEXT, from_status TEXT, to_status TEXT, at REAL, note TEXT);
CREATE TABLE IF NOT EXISTS site_publication(
  edition_id TEXT, revision INTEGER, content_sha256 TEXT, commit_ref TEXT, status TEXT,
  detail TEXT, at REAL, PRIMARY KEY(edition_id, revision));
CREATE TABLE IF NOT EXISTS edition_recipient(
  edition_id TEXT, revision INTEGER, recipient_key TEXT, recipient_label TEXT, frozen_at REAL,
  PRIMARY KEY(edition_id, revision, recipient_key));
CREATE TABLE IF NOT EXISTS delivery(
  edition_id TEXT, revision INTEGER, recipient_key TEXT, recipient_label TEXT, message_id TEXT,
  status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, updated_at REAL,
  PRIMARY KEY(edition_id, revision, recipient_key));
"""


class TransitionError(RuntimeError):
    pass


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), isolation_level=None, timeout=30)
    db.execute("PRAGMA journal_mode=WAL"); db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    have = {r[1] for r in db.execute("PRAGMA table_info(edition)")}
    for col in ("approval", "origin"):                      # migration for databases created before 2026-10-30 stabilisation
        if col not in have:
            db.execute(f"ALTER TABLE edition ADD COLUMN {col} TEXT")
    db.execute("UPDATE edition SET origin='sample' WHERE origin IS NULL AND edition_id LIKE 'sample-%'")
    return db


def recipient_key(address: str, salt: str = "hip-v1") -> str:
    return hashlib.sha256((salt + ":" + address.strip().lower()).encode()).hexdigest()


def recipient_label(address: str) -> str:
    """Non-identifying label for logs: first char + domain TLD class."""
    a = address.strip()
    return f"{a[:1]}***@***{a[a.rfind('.'):] if '.' in a else ''}"


def get(db, edition_id):
    r = db.execute("SELECT * FROM edition WHERE edition_id=?", (edition_id,)).fetchone()
    if not r:
        return None
    cols = [d[0] for d in db.execute("SELECT * FROM edition LIMIT 0").description]
    return dict(zip(cols, r))


def transition(db, edition_id, to, note="", **fields):
    db.execute("BEGIN IMMEDIATE")
    try:
        cur = get(db, edition_id)
        frm = cur["status"] if cur else None
        if to not in ALLOWED.get(frm, set()):
            raise TransitionError(f"{edition_id}: {frm} -> {to} not allowed")
        now = time.time()
        if cur is None:
            db.execute("INSERT INTO edition(edition_id,status,created_at,updated_at) VALUES(?,?,?,?)", (edition_id, to, now, now))
        else:
            if cur["content_sha256"] and fields.get("content_sha256") and fields["content_sha256"] != cur["content_sha256"] \
               and fields.get("revision", cur["revision"]) == cur["revision"] and frm not in (None, "pending_review", "prepared"):
                raise TransitionError(f"{edition_id}: content changed after freeze without a new revision")
            db.execute("UPDATE edition SET status=?, updated_at=? WHERE edition_id=?", (to, now, edition_id))
        for k, v in fields.items():
            db.execute(f"UPDATE edition SET {k}=? WHERE edition_id=?", (v, edition_id))
        db.execute("INSERT INTO transition(edition_id,from_status,to_status,at,note) VALUES(?,?,?,?,?)", (edition_id, frm, to, now, note))
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK"); raise


def delivery_status(db, edition_id, revision, key):
    r = db.execute("SELECT status, attempts FROM delivery WHERE edition_id=? AND revision=? AND recipient_key=?",
                   (edition_id, revision, key)).fetchone()
    return r if r else (None, 0)


def set_delivery(db, edition_id, revision, key, label, status, message_id=None, error=None, bump=False):
    db.execute("""INSERT INTO delivery(edition_id,revision,recipient_key,recipient_label,message_id,status,attempts,last_error,updated_at)
                  VALUES(?,?,?,?,?,?,?,?,?)
                  ON CONFLICT(edition_id,revision,recipient_key) DO UPDATE SET status=excluded.status,
                  message_id=COALESCE(excluded.message_id, delivery.message_id),
                  attempts=delivery.attempts + ?, last_error=excluded.last_error, updated_at=excluded.updated_at""",
               (edition_id, revision, key, label, message_id, status, 1 if bump else 0, error, time.time(), 1 if bump else 0))


def freeze_recipients(db, edition_id, revision, addresses: list[str]) -> int:
    """Record the expected recipient set once (keys only). Later calls keep the first set."""
    if db.execute("SELECT 1 FROM edition_recipient WHERE edition_id=? AND revision=?", (edition_id, revision)).fetchone():
        return expected_count(db, edition_id, revision)
    now = time.time()
    for a in addresses:
        db.execute("INSERT OR IGNORE INTO edition_recipient VALUES(?,?,?,?,?)", (edition_id, revision, recipient_key(a), recipient_label(a), now))
    return expected_count(db, edition_id, revision)


def expected_keys(db, edition_id, revision) -> set[str]:
    return {r[0] for r in db.execute("SELECT recipient_key FROM edition_recipient WHERE edition_id=? AND revision=?", (edition_id, revision))}


def expected_count(db, edition_id, revision) -> int:
    return len(expected_keys(db, edition_id, revision))


def delivery_complete(db, edition_id, revision) -> bool:
    """True only if a non-empty expected set was frozen and every member is `accepted`."""
    exp = expected_keys(db, edition_id, revision)
    if not exp:
        return False
    ok = {r[0] for r in db.execute("SELECT recipient_key FROM delivery WHERE edition_id=? AND revision=? AND status='accepted'", (edition_id, revision))}
    return exp <= ok


def recover(db) -> list[str]:
    """Called at start-up. Anything left `sending` by a crash becomes `unknown`."""
    rows = db.execute("SELECT edition_id, revision, recipient_label FROM delivery WHERE status='sending'").fetchall()
    db.execute("UPDATE delivery SET status='unknown', last_error='process ended while sending', updated_at=? WHERE status='sending'", (time.time(),))
    return [f"{e} r{r} {l}" for e, r, l in rows]


def summary(db) -> dict:
    ed = db.execute("SELECT status, count(*) FROM edition GROUP BY status").fetchall()
    dv = db.execute("SELECT status, count(*) FROM delivery GROUP BY status").fetchall()
    return {"editions": dict(ed), "deliveries": dict(dv)}

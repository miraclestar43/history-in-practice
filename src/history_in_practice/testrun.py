"""One tracked TEST edition (email + site preview), kept apart from production accounting.

* Identity: a test_id is chosen once and persisted (table test_run) together with the
  source edition, its revision and content_sha256, the labelled test object's hash, the
  site preview base URL and an explicit, bounded send window. Reruns reuse the record;
  a different source hash under the same id is refused (that would be a different test).
* The test object is the admitted final article with labels only: edition_id=test_id,
  status "test", 【测试】/[TEST] title prefix, a TEST banner in email and on the page.
  body_problems() proves sections, reflection, sources and further reading are unchanged.
* Nothing here touches the edition table, rotation, coverage or publication state.
  Deliveries use the existing per-recipient tables under the test_id: the recipient set
  is frozen on the first send; `accepted` and `unknown` are never resent; `failed` may be
  retried under the same id while the window is open.
* Window: set at creation (<= MAX_WINDOW_H hours), checked before every recipient
  (mailer.send_edition may_start). It can be renewed only while no recipient has been
  accepted, is unknown or is sending; each renewal is recorded.
* Site before send: the live preview's index + edition JSON must match the test object
  (site_export.verify: revision, content_sha256, recomputed hash) before any email starts.
* Source admission: at prepare, at the start of send and again before each recipient, the source
  must be admitted *now* (final_edit.current_eligibility: edition state, admitted path, revision and
  hash, final-editor record re-verified against article/evidence/base, approval naming the record)
  and still be the article this test was made from. A requeue or any change blocks unsent
  recipients; accepted/unknown rows stay as recorded. Demotions from `checked` take the same
  publish lock as `send`, so the check cannot go stale between a recipient's check and its send.
"""
from __future__ import annotations
import json, re, time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from . import render, site_export, mailer, state, final_edit

MAX_WINDOW_H = 12
TZ = ZoneInfo("America/Los_Angeles")
BODY_KEYS = ("sections", "reflection", "uncertainty_note", "sources", "further_reading", "category")
ID_RE = re.compile(r"^test-\d{8}-[a-z0-9-]{3,60}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS test_run(
  test_id TEXT PRIMARY KEY, source_edition TEXT NOT NULL, source_revision INTEGER NOT NULL,
  source_sha256 TEXT NOT NULL, test_sha256 TEXT NOT NULL, source_path TEXT NOT NULL,
  site_base TEXT, created_at REAL, window_opens REAL, window_expires REAL,
  site_verified_at REAL, site_detail TEXT, history TEXT NOT NULL DEFAULT '[]');
"""


class TestRunError(RuntimeError):
    pass


def init(db):
    db.executescript(SCHEMA)


def make_test_obj(src: dict, test_id: str, date: str) -> dict:
    o = json.loads(json.dumps(src))
    o.update(edition_id=test_id, status="test", edition_date=date, test={"source_edition": src["edition_id"],
             "source_revision": src["revision"], "source_sha256": src["content_sha256"]})
    o["title"] = {"zh": "【测试】" + src["title"]["zh"], "en": "[TEST] " + src["title"]["en"]}
    o.pop("edition_number", None)
    return render.finalize(o)


def body_problems(src: dict, test: dict) -> list[str]:
    p = [f"{k} differs from the source article" for k in BODY_KEYS if src.get(k) != test.get(k)]
    for lang, pre in (("zh", "【测试】"), ("en", "[TEST] ")):
        if test["title"][lang] != pre + src["title"][lang]:
            p.append(f"title.{lang} is not the source title with the TEST prefix")
    if render.finalize(json.loads(json.dumps(src)))["content_sha256"] != src["content_sha256"]:
        p.append("source content_sha256 does not match its content")
    return p


def get(db, test_id):
    init(db)
    r = db.execute("SELECT * FROM test_run WHERE test_id=?", (test_id,)).fetchone()
    if not r:
        return None
    cols = [d[0] for d in db.execute("SELECT * FROM test_run LIMIT 0").description]
    rec = dict(zip(cols, r)); rec["history"] = json.loads(rec["history"])
    return rec


def _log(db, test_id, event, **kw):
    rec = get(db, test_id); h = rec["history"] + [dict(at=round(time.time()), event=event, **kw)]
    db.execute("UPDATE test_run SET history=? WHERE test_id=?", (json.dumps(h, ensure_ascii=False), test_id))


def source_problems(db, edition_id: str, src_sha: str, src_path: Path | None = None) -> list[str]:
    """Current admission of the test's source, re-verified from the canonical records (see module doc)."""
    p, o = final_edit.current_eligibility(db, edition_id, src_path)
    if o is not None and o["content_sha256"] != src_sha:
        p.append(f"admitted content of {edition_id} is {o['content_sha256'][:12]}, not the {src_sha[:12]} this test was made from")
    return p


def create_or_load(db, test_id: str, src_path: Path, *, site_base: str, window_hours: float, now: float | None = None,
                   check_admission: bool = True) -> tuple[dict, dict]:
    """Return (record, test object). Creates the record once; afterwards it must match.
    check_admission=False only for read-only actions (status, verify-site, renew-window)."""
    if not ID_RE.match(test_id):
        raise TestRunError("test id must look like test-YYYYMMDD-short-name")
    if not 0 < window_hours <= MAX_WINDOW_H:
        raise TestRunError(f"window must be > 0 and <= {MAX_WINDOW_H} hours")
    src = json.loads(Path(src_path).read_text(encoding="utf-8"))
    if src.get("status") == "test":
        raise TestRunError("source is already a test object")
    if check_admission:
        sp = source_problems(db, src.get("edition_id", "?"), src.get("content_sha256", ""), src_path)
        if sp:
            raise TestRunError("source is not currently admitted: " + "; ".join(sp[:5]))
    now = time.time() if now is None else now
    rec = get(db, test_id)
    if rec:
        if rec["source_sha256"] != src["content_sha256"] or rec["source_edition"] != src["edition_id"]:
            raise TestRunError(f"{test_id} was created for {rec['source_edition']} {rec['source_sha256'][:12]}; "
                               "this article differs — a different test needs a different id")
        if site_base and rec["site_base"] and site_base.rstrip("/") != rec["site_base"]:
            raise TestRunError(f"{test_id} is bound to site preview {rec['site_base']}")
        if site_base and not rec["site_base"]:                   # bound once, e.g. after the preview host reports its URL
            db.execute("UPDATE test_run SET site_base=? WHERE test_id=?", (site_base.rstrip("/"), test_id))
            _log(db, test_id, "site_base_bound", site_base=site_base.rstrip("/")); rec = get(db, test_id)
        date = datetime.fromtimestamp(rec["created_at"], TZ).strftime("%Y-%m-%d")
    else:
        date = datetime.fromtimestamp(now, TZ).strftime("%Y-%m-%d")
    test = make_test_obj(src, test_id, date)
    bp = body_problems(src, test)
    if bp:
        raise TestRunError("; ".join(bp))
    if not rec:
        db.execute("INSERT INTO test_run(test_id,source_edition,source_revision,source_sha256,test_sha256,source_path,site_base,"
                   "created_at,window_opens,window_expires) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (test_id, src["edition_id"], src["revision"], src["content_sha256"], test["content_sha256"], str(src_path),
                    site_base.rstrip("/") if site_base else None, now, now, now + window_hours * 3600))
        _log(db, test_id, "created", window_hours=window_hours)
        rec = get(db, test_id)
    elif rec["test_sha256"] != test["content_sha256"]:
        raise TestRunError("test object hash changed under the same id (renderer or labels changed)")
    return rec, test


def correction(db, test_id: str, corrected_src: Path, note: dict, *, at: str, site_root: Path | None = None) -> dict:
    """A dated, versioned correction of an already-sent TEST: revision+1 built from the CURRENTLY admitted corrected source
    (same labels), carrying {at, note zh/en, previous revision + hash + its exact JSON at a versioned path}. The sent
    revision's record (test_sha256, source hash, deliveries) is never modified; nothing is emailed."""
    rec = get(db, test_id)
    if not rec:
        raise TestRunError(f"no test {test_id}")
    src = json.loads(Path(corrected_src).read_text(encoding="utf-8"))
    sp = source_problems(db, src.get("edition_id", "?"), src.get("content_sha256", ""), Path(corrected_src))
    if sp:
        raise TestRunError("corrected source is not currently admitted: " + "; ".join(sp[:4]))
    date = datetime.fromtimestamp(rec["created_at"], TZ).strftime("%Y-%m-%d")
    prev_rev = 1 + sum(1 for h in rec["history"] if h["event"] == "correction_published")
    new = make_test_obj(src, test_id, date); new["revision"] = prev_rev + 1
    bp = body_problems(src, new)
    if bp:
        raise TestRunError("; ".join(bp))
    y, m, d = date.split("-")
    prev_path = f"data/history/{y}/{m}/{d}-{test_id}.r{prev_rev}.json"
    new["correction"] = {"at": at, "note": note, "source_revision": src["revision"], "source_sha256": src["content_sha256"],
                         "previous": {"revision": prev_rev, "content_sha256": rec["test_sha256"] if prev_rev == 1 else None, "path": prev_path}}
    render.finalize(new)
    out = {"test_id": test_id, "revision": new["revision"], "test_sha256": new["content_sha256"], "previous_revision": prev_rev, "previous_path": prev_path}
    _log(db, test_id, "correction_published", **{k: v for k, v in out.items() if k != "test_id"}, at_la=at)
    return new


def window_open(rec, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    return rec["window_opens"] <= now < rec["window_expires"]


def renew_window(db, test_id, hours: float, now: float | None = None) -> dict:
    if not 0 < hours <= MAX_WINDOW_H:
        raise TestRunError(f"window must be > 0 and <= {MAX_WINDOW_H} hours")
    rec = get(db, test_id); now = time.time() if now is None else now
    sent = db.execute("SELECT count(*) FROM delivery WHERE edition_id=? AND status IN ('accepted','unknown','sending')", (test_id,)).fetchone()[0]
    if sent:
        raise TestRunError("a recipient was already accepted, is unknown or is sending: the window cannot be renewed")
    db.execute("UPDATE test_run SET window_opens=?, window_expires=? WHERE test_id=?", (now, now + hours * 3600, test_id))
    _log(db, test_id, "window_renewed", hours=hours)
    return get(db, test_id)


def verify_site(db, rec, test: dict, fetch=site_export.http_fetch) -> tuple[bool, list[str]]:
    if not rec["site_base"]:
        return False, ["no site preview base URL recorded for this test"]
    ok, problems = site_export.verify(test, rec["site_base"], fetch=fetch)
    if ok:
        db.execute("UPDATE test_run SET site_verified_at=?, site_detail=? WHERE test_id=?",
                   (time.time(), f"{rec['site_base']} r{test['revision']} {test['content_sha256'][:16]}", rec["test_id"]))
    _log(db, rec["test_id"], "site_verify", ok=ok, problems=problems[:5])
    return ok, problems


def deliveries(db, test_id, revision) -> list[dict]:
    return [{"recipient": l, "status": s, "attempts": n, "detail": e}
            for l, s, n, e in db.execute("SELECT recipient_label, status, attempts, last_error FROM delivery WHERE edition_id=? AND revision=? "
                                         "ORDER BY recipient_label", (test_id, revision))]


def send(db, rec, test: dict, runtime, *, base: str, out: Path, fetch=site_export.http_fetch, clock=time.time) -> dict:
    """Live site check, window check, then one tracked send per frozen recipient. Never resends accepted/unknown."""
    if not window_open(rec, clock()):
        _log(db, rec["test_id"], "send_refused", why="window closed")
        return {"sent": False, "reason": "test window is closed (renew only if nothing was sent)"}
    sp = source_problems(db, rec["source_edition"], rec["source_sha256"])
    if sp:
        _log(db, rec["test_id"], "send_refused", why="source not currently admitted", problems=sp[:5])
        return {"sent": False, "reason": "source is not currently admitted: " + "; ".join(sp[:3])}
    ok, problems = verify_site(db, rec, test, fetch=fetch)
    if not ok:
        return {"sent": False, "reason": "site preview does not serve this test object: " + "; ".join(problems[:3])}
    problems = mailer.validate_config(runtime)
    if problems:
        _log(db, rec["test_id"], "send_refused", why="config incomplete", problems=problems)
        return {"sent": False, "reason": "; ".join(problems)}
    render.build([dict(test)], out, base)
    html = (out / "email" / f"{test['edition_id']}.html").read_text(encoding="utf-8")
    text = (out / "email" / f"{test['edition_id']}.txt").read_text(encoding="utf-8")
    def may_start():                               # before each recipient: window, then the source's current admission
        if not window_open(rec, clock()):
            return False
        sp = source_problems(db, rec["source_edition"], rec["source_sha256"])
        if sp:
            _log(db, rec["test_id"], "recipient_blocked", why="source not currently admitted", problems=sp[:5])
            return "source not currently admitted: " + "; ".join(sp[:2])
        return True
    rep = mailer.send_edition(db, test, html, text, runtime, mode="real", manual_test=True, may_start=may_start)
    done = state.delivery_complete(db, test["edition_id"], test["revision"])
    _log(db, rec["test_id"], "send", all_accepted=done, statuses=[r["status"] for r in rep])
    return {"sent": True, "all_accepted": done, "report": rep, "deliveries": deliveries(db, test["edition_id"], test["revision"])}

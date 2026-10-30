"""Daily publication: schedule -> archive -> site commit -> live check -> email.

Each step records state and stops cleanly if its configuration is missing:
* site export needs SITE_REPO_PATH (a website working copy) in the runtime env;
  `git push` only happens with SITE_PUSH_ENABLED=true.
* live verification needs the edition's JSON to be served with the same
  revision and content_sha256 (see site_export.verify); otherwise email waits.
* email needs EMAIL_SEND_ENABLED=true and a complete configuration
  (mailer.validate_config); per-recipient state prevents resends and completion
  requires every frozen expected recipient to be accepted.

Asynchronous deploys: after the site commit, the live check is retried with
bounded backoff (project.json "site_wait") until the send deadline; a run that
still waits exits non-zero and the retry timer resumes it later the same day.
Past the deadline, or on a later day, an unfinished edition becomes `overdue`
(alerted, never sent late) and the rotation continues with a new edition.
A commit made while SITE_PUSH_ENABLED was false is pushed on a later run once
pushing is enabled (site_publication.status records committed/pushed).
"""
from __future__ import annotations
import fcntl, json, os, shutil, subprocess, time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from . import state, render, site_export, mailer
from .state import SCHEDULABLE_SQL
from .config import REPO, data_dir, load_project


@contextmanager
def lock(name="hip"):
    p = data_dir() / f"{name}.lock"; f = open(p, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(f"another {name} job holds {p}")
    try:
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN); f.close()


IN_FLIGHT = ("scheduled", "archived", "site_committed", "site_live", "email_pending")


def now_la() -> datetime:
    return datetime.now(ZoneInfo(load_project().get("timezone", "America/Los_Angeles")))


def today_la() -> str:
    return now_la().date().isoformat()


def past_deadline(date: str, now: datetime) -> bool:
    """True when `now` (tz-aware, LA) is after the send deadline of `date`."""
    hh, mm = map(int, load_project().get("send_deadline", "11:00").split(":"))
    dl = datetime.fromisoformat(date).replace(hour=hh, minute=mm, tzinfo=now.tzinfo)
    return now > dl


def expire_stale(db, today: str, now: datetime) -> list[str]:
    """In-flight editions from earlier days (or today's past the deadline) -> overdue. Never sends them."""
    out = []
    for eid, d, st in db.execute(f"SELECT edition_id, edition_date, status FROM edition WHERE status IN {IN_FLIGHT}").fetchall():
        if d and (d < today or (d == today and past_deadline(d, now))):
            state.transition(db, eid, "overdue", note=f"{st} not finished by the {d} deadline; not sent late; alert maintainer",
                             reason=f"overdue from {st} ({d})")
            out.append(f"{eid} ({d}, was {st})")
    return out


def next_category(db) -> str:
    rot = load_project()["rotation"]
    n = db.execute("SELECT count(*) FROM edition WHERE status IN ('archived','site_committed','site_live','email_pending','complete','scheduled','overdue')").fetchone()[0]
    return rot[n % len(rot)]


def schedule(db, date: str) -> dict | None:
    """Pick the oldest checked edition in the rotation's category. None = skip + alert."""
    cur = db.execute("SELECT edition_id FROM edition WHERE edition_date=? AND status IN "
                     "('scheduled','archived','site_committed','site_live','email_pending','complete')", (date,)).fetchone()   # resume in-flight
    if cur:
        return state.get(db, cur[0])
    cat = next_category(db)
    row = db.execute("SELECT edition_id FROM edition WHERE status='checked' AND category=? AND " + SCHEDULABLE_SQL + " ORDER BY updated_at LIMIT 1",
                     (cat,)).fetchone()
    if not row:
        return None
    num = db.execute("SELECT count(*) FROM edition WHERE status NOT IN ('checked','prepared','pending_review','rejected','overdue')").fetchone()[0] + 1
    state.transition(db, row[0], "scheduled", note=f"scheduled for {date} ({cat}) as #{num}", edition_date=date)
    return state.get(db, row[0]) | {"edition_number": num}


def content_dir() -> Path:
    return Path(os.environ.get("HIP_CONTENT_DIR", REPO / "content"))


def archive(db, ed: dict, content_root: Path | None = None) -> Path:
    o = json.loads(Path(ed["path"]).read_text(encoding="utf-8"))
    o.update(edition_date=ed["edition_date"], status="published")
    render.finalize(o)
    y, m, d = ed["edition_date"].split("-")
    root = Path(content_root or content_dir()) / y / m; root.mkdir(parents=True, exist_ok=True)
    base = root / f"{d}-{o['edition_id']}"
    base.with_suffix(".json").write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(str(base) + ".zh.md").write_text(render.markdown(o, "zh"), encoding="utf-8")
    Path(str(base) + ".en.md").write_text(render.markdown(o, "en"), encoding="utf-8")
    state.transition(db, ed["edition_id"], "archived", note=str(base), path=str(base.with_suffix(".json")), content_sha256=o["content_sha256"])
    return base.with_suffix(".json")


def commit_site(db, ed: dict, site_repo: Path, objs: list[dict], push: bool) -> str:
    written = site_export.export(objs, site_repo)
    git = ["git", "-C", str(site_repo)]
    subprocess.run(git + ["add", "--", *site_export.ALLOWED_PREFIXES], check=True)
    staged = subprocess.run(git + ["diff", "--cached", "--name-only"], capture_output=True, text=True, check=True).stdout.split()
    stray = [p for p in staged if not p.startswith(site_export.ALLOWED_PREFIXES)]
    if stray:
        subprocess.run(git + ["reset", "-q"], check=True)
        raise site_export.ExportError(f"refusing to commit paths outside allow-list: {stray}")
    if staged:
        subprocess.run(git + ["commit", "-q", "-m", f"history: {ed['edition_id']} r{ed['revision']}"], check=True)
    ref = subprocess.run(git + ["rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if push:
        subprocess.run(git + ["push", "-q"], check=True)        # no --force, ever
    _publication(db, ed, ref, "pushed" if push else "committed")
    state.transition(db, ed["edition_id"], "site_committed", note=f"{ref} push={push} files={len(written)}")
    return ref


def _publication(db, ed, ref, status):
    db.execute("INSERT INTO site_publication(edition_id,revision,content_sha256,commit_ref,status,detail,at) VALUES(?,?,?,?,?,?,?) "
               "ON CONFLICT(edition_id,revision) DO UPDATE SET commit_ref=excluded.commit_ref, status=excluded.status, at=excluded.at",
               (ed["edition_id"], ed["revision"], ed.get("content_sha256"), ref, status, "", time.time()))


def push_pending(db, ed, site_repo: Path) -> str:
    """Push a commit recorded while pushing was disabled. Returns the publication status."""
    row = db.execute("SELECT status FROM site_publication WHERE edition_id=? AND revision=?", (ed["edition_id"], ed["revision"])).fetchone()
    if row and row[0] == "committed":
        subprocess.run(["git", "-C", str(site_repo), "push", "-q"], check=True)
        ref = subprocess.run(["git", "-C", str(site_repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        _publication(db, ed, ref, "pushed")
        return "pushed"
    return row[0] if row else "unknown"


def wait_live(obj, base, fetch, *, deadline_ok, sleep=time.sleep) -> tuple[bool, list[str], int]:
    """Bounded backoff on the live check; stops early once past the deadline."""
    sched = load_project().get("site_wait", {}).get("backoff_s", [60, 120, 240, 300, 300, 300])
    ok, problems = site_export.verify(obj, base, fetch=fetch); tries = 1
    for delay in sched:
        if ok or not deadline_ok():
            break
        sleep(delay); ok, problems = site_export.verify(obj, base, fetch=fetch); tries += 1
    return ok, problems, tries


def publish_today(db, runtime, *, date: str | None = None, fetch=site_export.http_fetch, clock=None, sleep=time.sleep) -> dict:
    clock = clock or now_la; now = clock(); date = date or now.date().isoformat(); rep = {"date": date}
    stale = expire_stale(db, date, now)
    if stale:
        rep["overdue"] = stale                       # alerted, never sent late
    if past_deadline(date, now) and not db.execute("SELECT 1 FROM edition WHERE edition_date=? AND status='complete'", (date,)).fetchone():
        rep.update(outcome="overdue", reason=f"past the {date} send deadline; nothing scheduled or sent late"); return rep
    ed = schedule(db, date)
    if not ed:
        rep.update(outcome="skipped", reason=f"no checked edition in category {next_category(db)}; alert maintainer"); return rep
    rep["edition_id"] = ed["edition_id"]
    if ed["status"] == "complete":
        rep.update(outcome="complete", reason="already complete; nothing resent"); return rep
    if ed["status"] == "scheduled":
        archive(db, ed); ed = state.get(db, ed["edition_id"])
    obj = json.loads(Path(ed["path"]).read_text(encoding="utf-8"))
    if ed["status"] == "archived":
        site_repo = runtime.get("SITE_REPO_PATH")
        if not site_repo:
            rep.update(outcome="waiting", reason="SITE_REPO_PATH not configured; site step not run"); return rep
        archived = [json.loads(p.read_text()) for p in sorted(content_dir().rglob("*.json"))]
        rep["site_commit"] = commit_site(db, ed, Path(site_repo), archived, push=runtime.get("SITE_PUSH_ENABLED", "false") == "true")
        ed = state.get(db, ed["edition_id"])
    if ed["status"] == "site_committed":
        push_ok = runtime.get("SITE_PUSH_ENABLED", "false") == "true"
        pub = push_pending(db, ed, Path(runtime.get("SITE_REPO_PATH"))) if push_ok and runtime.get("SITE_REPO_PATH") else \
            (db.execute("SELECT status FROM site_publication WHERE edition_id=? AND revision=?", (ed["edition_id"], ed["revision"])).fetchone() or ["unknown"])[0]
        if pub == "committed":
            rep.update(outcome="waiting", reason="site commit is local only: SITE_PUSH_ENABLED is false; enable it and rerun to push"); return rep
        ok, problems, tries = wait_live(obj, runtime.get("SITE_BASE_URL", "https://starhub.vip"), fetch,
                                        deadline_ok=lambda: not past_deadline(date, clock()), sleep=sleep)
        rep["live_checks"] = tries
        if not ok:
            rep.update(outcome="waiting", reason=f"live check failed after {tries} tries: " + "; ".join(problems) +
                       "; the retry timer resumes before the deadline, then it becomes overdue"); return rep
        state.transition(db, ed["edition_id"], "site_live", note="verified content_sha256"); ed = state.get(db, ed["edition_id"])
    if ed["status"] == "site_live":
        state.transition(db, ed["edition_id"], "email_pending"); ed = state.get(db, ed["edition_id"])
    if ed["status"] == "email_pending":
        if not runtime.send_enabled:
            rep.update(outcome="waiting", reason="EMAIL_SEND_ENABLED is false"); return rep
        problems = mailer.validate_config(runtime)
        if problems:
            rep.update(outcome="waiting", reason="email configuration incomplete: " + "; ".join(problems)); return rep
        out = data_dir() / "outbox"; render.build([dict(obj)], out, runtime.get("SITE_BASE_URL", "https://starhub.vip"))
        html = (out / "email" / f"{obj['edition_id']}.html").read_text(encoding="utf-8"); text = (out / "email" / f"{obj['edition_id']}.txt").read_text(encoding="utf-8")
        rep["deliveries"] = mailer.send_edition(db, obj, html, text, runtime, mode="real")
        done = state.delivery_complete(db, obj["edition_id"], obj["revision"])
        rep["expected_recipients"] = state.expected_count(db, obj["edition_id"], obj["revision"])
        if done:
            state.transition(db, ed["edition_id"], "complete")
        rep["outcome"] = "complete" if done else "partial"
    return rep


EXIT = {"complete": 0, "partial": 3, "skipped": 4, "waiting": 5, "overdue": 6}

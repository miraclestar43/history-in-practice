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
(alerted, never sent late) and the mix plan continues with a new edition.
The deadline is re-checked after every wait and every fetch (a sleep never
runs past it), before email starts, and before each recipient's send: a
recipient whose SMTP exchange began before the deadline keeps its actual
result (accepted/failed/unknown); no new send starts after it.
A commit made while SITE_PUSH_ENABLED was false is pushed on a later run once
pushing is enabled (site_publication.status records committed/pushed).
"""
from __future__ import annotations
import fcntl, json, os, shutil, subprocess, time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from . import state, render, site_export, mailer, news
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


def deadline_at(date: str, tz) -> datetime:
    hh, mm = map(int, load_project().get("send_deadline", "11:00").split(":"))
    return datetime.fromisoformat(date).replace(hour=hh, minute=mm, tzinfo=tz)


def send_at(date: str, tz) -> datetime:
    hh, mm = map(int, load_project().get("send_time", "07:30").split(":"))
    return datetime.fromisoformat(date).replace(hour=hh, minute=mm, tzinfo=tz)


def past_deadline(date: str, now: datetime) -> bool:
    """True when `now` (tz-aware, LA) is after the send deadline of `date`."""
    return now > deadline_at(date, now.tzinfo)


def seconds_left(date: str, now: datetime) -> float:
    return (deadline_at(date, now.tzinfo) - now).total_seconds()


def expire_stale(db, today: str, now: datetime) -> list[str]:
    """In-flight editions from earlier days (or today's past the deadline) -> overdue. Never sends them."""
    out = []
    for eid, d, st in db.execute(f"SELECT edition_id, edition_date, status FROM edition WHERE status IN {IN_FLIGHT}").fetchall():
        if d and (d < today or (d == today and past_deadline(d, now))):
            state.transition(db, eid, "overdue", note=f"{st} not finished by the {d} deadline; not sent late; alert maintainer",
                             reason=f"overdue from {st} ({d})")
            out.append(f"{eid} ({d}, was {st})")
    return out


def position(db) -> int:
    """Pattern position of the next edition = editions already scheduled or published (TEST editions are not editions)."""
    return db.execute("SELECT count(*) FROM edition WHERE status IN ('archived','site_committed','site_live','email_pending','complete','scheduled','overdue')").fetchone()[0]


def next_category(db) -> str:
    """Category of the edition the stored/derived plan would use next (kept for messages)."""
    from .pipeline import inventory
    return inventory(db, verify=True).get("next_category") or "none"


def schedule(db, date: str) -> dict | None:
    """The edition for this date: an in-flight one (resume), else the stored plan's next position if still eligible, else a
    fresh mix plan from this position (persisted; see mix.py). None = skip + alert."""
    cur = db.execute("SELECT edition_id FROM edition WHERE edition_date=? AND status IN "
                     "('scheduled','archived','site_committed','site_live','email_pending','complete')", (date,)).fetchone()   # resume in-flight
    if cur:
        return state.get(db, cur[0])
    from .final_edit import current_eligibility
    from . import mix
    from .pipeline import mix_history, _article_at
    pos = position(db); planned = mix.stored(db, pos); row = None
    if planned and planned[0]["position"] == pos and planned[0]["status"] == "planned":
        eid = planned[0]["edition_id"]; cur = state.get(db, eid)
        if cur and cur["status"] == "checked" and not current_eligibility(db, eid)[0]:
            row, cat = (eid,), cur["category"]               # the stored plan: retries and resumes reuse it
    if not row:                                             # no plan, or its next pick is no longer eligible: re-plan from here
        pool = []
        for eid, c, upd in db.execute("SELECT edition_id, category, updated_at FROM edition WHERE status='checked' AND " + SCHEDULABLE_SQL).fetchall():
            if c in mix.GROUP and not current_eligibility(db, eid)[0]:       # admitted *now*: final-editor record + clean context review
                pool.append(mix.item(eid, c, _article_at(db, eid), upd or 0))
        seq = mix.plan(pool, max(14, len(pool)), pos, history=mix_history(db))
        if not seq:
            return None
        mix.persist(db, pos, seq, "re-planned at scheduling" if planned else "planned at scheduling")
        row, cat = (seq[0]["edition_id"],), seq[0]["category"]
    mix.mark_used(db, pos, row[0])
    num = db.execute("SELECT count(*) FROM edition WHERE status NOT IN ('checked','prepared','pending_review','rejected','overdue')").fetchone()[0] + 1
    state.transition(db, row[0], "scheduled", note=f"scheduled for {date} ({cat}) as #{num}", edition_date=date)
    return state.get(db, row[0]) | {"edition_number": num}


def content_dir() -> Path:
    return Path(os.environ.get("HIP_CONTENT_DIR", REPO / "content"))


def archive(db, ed: dict, content_root: Path | None = None) -> Path:
    o = json.loads(Path(ed["path"]).read_text(encoding="utf-8"))
    src = render.finalize(json.loads(json.dumps(o)))
    o.update(edition_date=ed["edition_date"], status="published",
             admitted_from={"path": str(Path(ed["path"]).resolve()), "content_sha256": src["content_sha256"], "revision": ed["revision"],
                            "approval": ed.get("approval")})           # send_problems re-verifies this source before every recipient
    render.finalize(o)
    y, m, d = ed["edition_date"].split("-")
    root = Path(content_root or content_dir()) / y / m; root.mkdir(parents=True, exist_ok=True)
    base = root / f"{d}-{o['edition_id']}"
    base.with_suffix(".json").write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(str(base) + ".zh.md").write_text(render.markdown(o, "zh"), encoding="utf-8")
    Path(str(base) + ".en.md").write_text(render.markdown(o, "en"), encoding="utf-8")
    state.transition(db, ed["edition_id"], "archived", note=str(base), path=str(base.with_suffix(".json")), content_sha256=o["content_sha256"])
    return base.with_suffix(".json")


def news_binding(ed: dict, runtime, now: datetime) -> dict:
    """The news digest this edition revision carries -- frozen on first use, reused by every retry (news.bind).
    Never raises: missing, stale, damaged or unqualified news binds "absent" and the story goes out alone."""
    return news.bind(data_dir() / "news_bindings", ed, runtime.get("NEWS_EXPORT_DIR"),
                     runtime.get("SITE_BASE_URL", "https://starhub.vip"), now)


def commit_site(db, ed: dict, site_repo: Path, objs: list[dict], push: bool, extra: dict[str, str] | None = None) -> str:
    written = site_export.export(objs, site_repo)
    for rel, text in (extra or {}).items():                 # the bound news archive page (history/news/<date>/)
        dest = site_export._safe_dest(site_repo, rel); dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8"); written.append(rel)
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


def wait_live(obj, base, fetch, *, remaining, sleep=time.sleep) -> tuple[bool, list[str], int]:
    """Bounded backoff on the live check. `remaining()` = seconds to the send deadline: no wait runs past it
    and no new check starts after it. The caller re-checks the deadline after the last fetch."""
    sched = load_project().get("site_wait", {}).get("backoff_s", [60, 120, 240, 300, 300, 300])
    ok, problems = site_export.verify(obj, base, fetch=fetch); tries = 1
    for delay in sched:
        left = remaining()
        if ok or left <= 0:
            break
        sleep(min(delay, left))
        if remaining() < 0:
            break
        ok, problems = site_export.verify(obj, base, fetch=fetch); tries += 1
    return ok, problems, tries


def publish_today(db, runtime, *, date: str | None = None, fetch=site_export.http_fetch, clock=None, sleep=time.sleep) -> dict:
    clock = clock or now_la; now = clock(); date = date or now.date().isoformat(); rep = {"date": date}

    def late(why):                                   # crossed the deadline inside this run: overdue now, never sent late
        cur = state.get(db, rep["edition_id"])
        if cur["status"] in IN_FLIGHT:
            state.transition(db, rep["edition_id"], "overdue", note=why[:500], reason=why[:2000])
        rep.update(outcome="overdue", reason=why)
        return rep
    stale = expire_stale(db, date, now)
    if stale:
        rep["overdue"] = stale                       # alerted, never sent late
    if past_deadline(date, now) and not db.execute("SELECT 1 FROM edition WHERE edition_date=? AND status='complete'", (date,)).fetchone():
        rep.update(outcome="overdue", reason=f"past the {date} send deadline; nothing scheduled or sent late"); return rep
    if now < send_at(date, now.tzinfo) and not db.execute(f"SELECT 1 FROM edition WHERE edition_date=? AND status IN {IN_FLIGHT + ('complete',)}",
                                                          (date,)).fetchone():
        # launch 2026-11-01: an early run (manual, a catch-up timer) starts nothing -- no schedule, site or email before send_time
        rep.update(outcome="waiting", reason=f"before the {load_project().get('send_time')} send time ({now.tzinfo}); nothing started"); return rep
    ed = schedule(db, date)
    if not ed:
        rep.update(outcome="skipped", reason=f"no eligible edition for plan position {position(db)} (mix: ~4 China / 3 elsewhere per 7); alert maintainer"); return rep
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
        nb = news_binding({**ed, "edition_date": obj.get("edition_date") or date}, runtime, now)
        rep["news"] = {k: nb.get(k) for k in ("status", "snapshot_id", "text_sha256", "reason")}
        rep["site_commit"] = commit_site(db, ed, Path(site_repo), archived, push=runtime.get("SITE_PUSH_ENABLED", "false") == "true",
                                         extra=news.site_files(nb))
        ed = state.get(db, ed["edition_id"])
    if ed["status"] == "site_committed":
        push_ok = runtime.get("SITE_PUSH_ENABLED", "false") == "true"
        pub = push_pending(db, ed, Path(runtime.get("SITE_REPO_PATH"))) if push_ok and runtime.get("SITE_REPO_PATH") else \
            (db.execute("SELECT status FROM site_publication WHERE edition_id=? AND revision=?", (ed["edition_id"], ed["revision"])).fetchone() or ["unknown"])[0]
        if pub == "committed":
            rep.update(outcome="waiting", reason="site commit is local only: SITE_PUSH_ENABLED is false; enable it and rerun to push"); return rep
        ok, problems, tries = wait_live(obj, runtime.get("SITE_BASE_URL", "https://starhub.vip"), fetch,
                                        remaining=lambda: seconds_left(date, clock()), sleep=sleep)
        rep["live_checks"] = tries
        if ok:
            state.transition(db, ed["edition_id"], "site_live", note="verified content_sha256"); ed = state.get(db, ed["edition_id"])
        if past_deadline(date, clock()):            # the wait or the last fetch crossed the deadline
            return late(f"site {'went live' if ok else 'not live'} only after the {date} send deadline; email not sent")
        if not ok:
            rep.update(outcome="waiting", reason=f"live check failed after {tries} tries: " + "; ".join(problems) +
                       "; the retry timer resumes before the deadline, then it becomes overdue"); return rep
    if ed["status"] == "site_live":
        state.transition(db, ed["edition_id"], "email_pending"); ed = state.get(db, ed["edition_id"])
    if ed["status"] == "email_pending":
        if not runtime.send_enabled:
            rep.update(outcome="waiting", reason="EMAIL_SEND_ENABLED is false"); return rep
        problems = mailer.validate_config(runtime)
        if problems:
            rep.update(outcome="waiting", reason="email configuration incomplete: " + "; ".join(problems)); return rep
        if past_deadline(date, clock()):
            return late(f"past the {date} send deadline before email started; nothing sent")
        nb = news.read_binding(data_dir() / "news_bindings", ed)    # read-only: the email never binds news itself
        rep["news"] = {k: nb.get(k) for k in ("status", "snapshot_id", "text_sha256", "reason")}
        out = data_dir() / "outbox"; render.build([dict(obj)], out, runtime.get("SITE_BASE_URL", "https://starhub.vip"),
                                                  news={obj["edition_id"]: nb})
        html = (out / "email" / f"{obj['edition_id']}.html").read_text(encoding="utf-8"); text = (out / "email" / f"{obj['edition_id']}.txt").read_text(encoding="utf-8")
        from .final_edit import send_problems
        sp = send_problems(db, obj)
        if sp:
            rep.update(outcome="waiting", reason="edition not currently eligible to send: " + "; ".join(sp[:3])); return rep

        def may_start():                               # before each recipient: deadline, then current eligibility
            if past_deadline(date, clock()):
                return False
            sp = send_problems(db, obj)
            return True if not sp else "not currently eligible: " + "; ".join(sp[:2])
        rep["deliveries"] = mailer.send_edition(db, obj, html, text, runtime, mode="real", may_start=may_start)
        done = state.delivery_complete(db, obj["edition_id"], obj["revision"])
        rep["expected_recipients"] = state.expected_count(db, obj["edition_id"], obj["revision"])
        if done:
            state.transition(db, ed["edition_id"], "complete")
            rep["outcome"] = "complete"
        elif any(d["status"] == "not_started_deadline" for d in rep["deliveries"]):
            acc = sum(d["status"] == "accepted" for d in rep["deliveries"])
            return late(f"send deadline passed during sending: {acc} accepted before it, the rest not sent (recorded per recipient)")
        else:
            rep["outcome"] = "partial"
    return rep


EXIT = {"complete": 0, "partial": 3, "skipped": 4, "waiting": 5, "overdue": 6}

"""Daily publication: schedule -> archive -> site commit -> live check -> email.

Each step records state and stops cleanly if its configuration is missing:
* site export needs SITE_REPO_PATH (a website working copy) in the runtime env;
  `git push` only happens with SITE_PUSH_ENABLED=true.
* live verification needs the edition's JSON to be served with the same
  revision and content_sha256 (see site_export.verify); otherwise email waits.
* email needs EMAIL_SEND_ENABLED=true; per-recipient state prevents resends.
"""
from __future__ import annotations
import fcntl, json, os, shutil, subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from . import state, render, site_export, mailer
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


def today_la() -> str:
    return datetime.now(ZoneInfo(load_project().get("timezone", "America/Los_Angeles"))).date().isoformat()


def next_category(db) -> str:
    rot = load_project()["rotation"]
    n = db.execute("SELECT count(*) FROM edition WHERE status IN ('archived','site_committed','site_live','email_pending','complete','scheduled')").fetchone()[0]
    return rot[n % len(rot)]


def schedule(db, date: str) -> dict | None:
    """Pick the oldest checked edition in the rotation's category. None = skip + alert."""
    cur = db.execute("SELECT edition_id FROM edition WHERE edition_date=? AND status IN "
                     "('scheduled','archived','site_committed','site_live','email_pending','complete')", (date,)).fetchone()   # resume in-flight
    if cur:
        return state.get(db, cur[0])
    cat = next_category(db)
    row = db.execute("SELECT edition_id FROM edition WHERE status='checked' AND category=? ORDER BY updated_at LIMIT 1", (cat,)).fetchone()
    if not row:
        return None
    num = db.execute("SELECT count(*) FROM edition WHERE status NOT IN ('checked','prepared','pending_review','rejected')").fetchone()[0] + 1
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
    state.transition(db, ed["edition_id"], "site_committed", note=f"{ref} push={push} files={len(written)}")
    return ref


def publish_today(db, runtime, *, date: str | None = None, fetch=site_export.http_fetch) -> dict:
    date = date or today_la(); rep = {"date": date}
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
        ok, problems = site_export.verify(obj, runtime.get("SITE_BASE_URL", "https://starhub.vip"), fetch=fetch)
        if not ok:
            rep.update(outcome="waiting", reason="live check failed: " + "; ".join(problems)); return rep
        state.transition(db, ed["edition_id"], "site_live", note="verified content_sha256"); ed = state.get(db, ed["edition_id"])
    if ed["status"] == "site_live":
        state.transition(db, ed["edition_id"], "email_pending"); ed = state.get(db, ed["edition_id"])
    if ed["status"] == "email_pending":
        if not runtime.send_enabled:
            rep.update(outcome="waiting", reason="EMAIL_SEND_ENABLED is false"); return rep
        out = data_dir() / "outbox"; render.build([dict(obj)], out, runtime.get("SITE_BASE_URL", "https://starhub.vip"))
        html = (out / "email" / f"{obj['edition_id']}.html").read_text(encoding="utf-8"); text = (out / "email" / f"{obj['edition_id']}.txt").read_text(encoding="utf-8")
        rep["deliveries"] = mailer.send_edition(db, obj, html, text, runtime, mode="real")
        if all(d["status"] == "accepted" for d in rep["deliveries"]):
            state.transition(db, ed["edition_id"], "complete")
        rep["outcome"] = "complete" if all(d["status"] == "accepted" for d in rep["deliveries"]) else "partial"
    return rep

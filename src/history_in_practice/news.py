"""The news digest at the end of the reading email (owner, 2026-11-01; supersedes prompts/08's news-first layout).

news-intel writes one frozen, verified brief per Beijing edition date (schema news-intel/brief-v1, under its
data/exports/brief/<date>/). This module only CONSUMES it:
  - check(snapshot, edition_date, now): schema, the snapshot's own text_sha256, the same Beijing edition date, a
    cutoff not in the future and at most NEWS_MAX_AGE_H old, Asia/Shanghai, 1-5 items (a real short day is fine;
    0 means no news), every item with a brief line and a source link;
  - bind(edition, ...): the first time an edition revision reaches the site step, the digest it will carry is
    frozen next to the edition (data/news_bindings/<edition_id>-r<revision>.json): snapshot_id, text_sha256, the
    digest text and HTML, the archive page. Every later render and every retry use that binding, never a newer
    snapshot; a binding that says "absent" stays absent.
Nothing here can stop the story: any missing, stale, damaged or unqualified snapshot -- or any error at all --
binds "absent" with its reason, and the email goes out with the story only. No news is generated, selected or
rewritten here; the newsletter does not wait for news.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = "news-intel/brief-v1"
NEWS_MAX_AGE_H = 26
BEIJING = timezone(timedelta(hours=8))
READER_KEYS = ("headline", "what", "why", "why_kind", "brief_line", "sources")
ACCENT = "#8b4513"


def _canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def text_sha256(snap: dict) -> str:
    """Same definition as news-intel's brief/snapshot.text_sha256: edition, cutoff and every item's reader text."""
    content = {"edition_date": snap["edition_date"], "cutoff": snap["cutoff"],
               "items": [{k: it.get(k) for k in READER_KEYS} for it in snap["items"]]}
    return hashlib.sha256(_canonical(content).encode()).hexdigest()


def load(export_dir: Path, edition_date: str) -> tuple[dict | None, str | None]:
    """(snapshot, archive_html) named by <edition_date>/current.json, or (None, None) when there is none."""
    d = Path(export_dir) / edition_date
    pointer = d / "current.json"
    if not pointer.exists():
        return None, None
    ref = json.loads(pointer.read_text(encoding="utf-8"))
    snap = json.loads((d / ref["file"]).read_text(encoding="utf-8"))
    page = d / f"{snap['snapshot_id']}.archive.html"
    return snap, (page.read_text(encoding="utf-8") if page.exists() else None)


def check(snap: dict | None, edition_date: str, now: datetime) -> list[str]:
    if not snap:
        return ["no news snapshot for this edition date"]
    p = []
    if snap.get("schema") != SCHEMA:
        p.append(f"schema {snap.get('schema')!r}")
        return p
    try:
        if text_sha256(snap) != snap.get("text_sha256"):
            p.append("text does not match its text_sha256 (damaged or edited)")
    except (KeyError, TypeError):
        p.append("snapshot is incomplete")
        return p
    if snap.get("edition_date") != edition_date:
        p.append(f"edition date {snap.get('edition_date')} is not {edition_date}")
    if snap.get("timezone") != "Asia/Shanghai":
        p.append(f"time zone {snap.get('timezone')!r}")
    try:
        cutoff = datetime.fromisoformat(snap["cutoff"])
        age = (now - cutoff).total_seconds() / 3600
        if age < -0.01:
            p.append(f"cutoff {snap['cutoff']} is in the future")
        elif age > NEWS_MAX_AGE_H:
            p.append(f"cutoff {snap['cutoff']} is {age:.1f} h old (max {NEWS_MAX_AGE_H} h)")
        if cutoff.astimezone(BEIJING).date().isoformat() != edition_date:
            p.append("cutoff is not on the edition's Beijing date")
    except (KeyError, ValueError, TypeError):
        p.append("cutoff missing or not ISO")
    items = snap.get("items") or []
    if snap.get("status") not in ("ready", "short") or not 1 <= len(items) <= 5:
        p.append(f"status {snap.get('status')!r} with {len(items)} items (1-5 needed)")
    for i, it in enumerate(items, start=1):
        if not (it.get("headline") and it.get("brief_line")):
            p.append(f"item {i}: headline/brief line missing")
        if not any(str(s.get("url", "")).startswith(("https://", "http://")) for s in it.get("sources") or []):
            p.append(f"item {i}: no source link")
    return p


def archive_url(snap: dict, base: str) -> str:
    return f"{base.rstrip('/')}/history/news/{snap['edition_date']}/"


def digest(snap: dict, base: str) -> dict:
    """The closing digest: the brief's own lines (no new text), its cutoff label and the full-news link."""
    c = datetime.fromisoformat(snap["cutoff"]).astimezone(BEIJING)
    head = f"今日新闻速览（截至北京时间{c.month}月{c.day}日{c:%H:%M}）"
    url = archive_url(snap, base)
    lines = [it["brief_line"] for it in snap["items"]]
    text = "\n".join(["== " + head + " ==", *[f"· {x}" for x in lines], f"完整新闻与来源：{url}"])
    lis = "".join(f'<li style="margin:0 0 6px;">{html.escape(x)}</li>' for x in lines)
    frag = (f'<hr style="border:none;border-top:1px solid #d8d2c8;margin:30px 0 18px;"><a id="news"></a>'
            f'<h3 style="font-size:15px;color:#55524d;margin:0 0 8px;">{html.escape(head)}</h3>'
            f'<ul style="font-size:15px;line-height:1.75;color:#24221f;margin:0 0 8px;padding-left:18px;">{lis}</ul>'
            f'<p style="font-size:14px;margin:0 0 4px;"><a href="{html.escape(url)}" style="color:{ACCENT};">完整新闻与来源</a>'
            f'<span style="color:#8a857d;"> · 自动选题、逐条核验，{len(lines)} 条</span></p>')
    return {"text": text, "html": frag, "url": url, "zh_chars": len(re.findall(r"[一-鿿]", "".join(lines) + head))}


def page_problems(page: str | None, snap: dict) -> list[str]:
    """The archive page must name this very snapshot (meta news-intel-snapshot / news-intel-text-sha256): any other
    HTML -- an older revision, another day, an empty file -- is not the page the digest may link to."""
    if not page or not page.strip():
        return ["archive page missing (the digest's link would not resolve)"]
    sid = re.search(r'<meta name="news-intel-snapshot" content="([^"]+)"', page)
    sha = re.search(r'<meta name="news-intel-text-sha256" content="([0-9a-f]{64})"', page)
    if not (sid and sha):
        return ["archive page does not name its snapshot"]
    if sid.group(1) != snap.get("snapshot_id") or sha.group(1) != snap.get("text_sha256"):
        return [f"archive page is {sid.group(1)}/{sha.group(1)[:12]}, not {snap.get('snapshot_id')}/"
                f"{str(snap.get('text_sha256'))[:12]}"]
    return []


def _write(path: Path, text: str) -> None:
    """Durable: written, fsynced, renamed, directory fsynced -- or an OSError."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    dfd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def binding_path(bindings_dir: Path, edition_id: str, revision) -> Path:
    return Path(bindings_dir) / f"{edition_id}-r{revision}.json"


def read_binding(bindings_dir: Path, edition: dict) -> dict:
    """The binding made at the site step, read-only -- what every email render and retry uses. No binding file
    means no news: an email step can never bind news itself, so a retry after some recipients were sent can never
    add news (or another version of it) that the first recipients did not get. Never raises."""
    path = binding_path(bindings_dir, edition["edition_id"], edition["revision"])
    try:
        if not path.exists():
            return {"status": "absent", "reason": "no binding was made at the site step; story only"}
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("status") == "bound" and not (rec.get("digest") or {}).get("html"):
            return {"status": "absent", "reason": "binding incomplete; story only"}
        return rec
    except (OSError, ValueError) as exc:
        return {"status": "absent", "reason": f"binding unreadable ({type(exc).__name__}); story only"}


def bind(bindings_dir: Path, edition: dict, export_dir: Path | None, base: str, now: datetime, *,
         persist: bool = True) -> dict:
    """The digest this edition revision carries, made once at the site step (an existing binding is returned as
    it is). persist=False: a preview that freezes nothing. A binding that cannot be saved durably is reported
    'absent' -- unsaved news never reaches an email. Never raises."""
    path = binding_path(bindings_dir, edition["edition_id"], edition["revision"])
    if path.exists():
        return read_binding(bindings_dir, edition)
    rec = {"edition_id": edition["edition_id"], "revision": edition["revision"],
           "edition_date": edition.get("edition_date"), "bound_at": now.isoformat(timespec="seconds")}
    try:
        if not export_dir:
            rec.update(status="absent", reason="NEWS_EXPORT_DIR not configured")
        else:
            snap, page = load(Path(export_dir), str(edition["edition_date"]))
            problems = check(snap, str(edition["edition_date"]), now)
            if snap and not problems:
                problems = page_problems(page, snap)
            if problems:
                rec.update(status="absent", reason="; ".join(problems)[:500],
                           snapshot_id=(snap or {}).get("snapshot_id"))
            else:
                d = digest(snap, base)
                rec.update(status="bound", snapshot_id=snap["snapshot_id"], text_sha256=snap["text_sha256"],
                           items=len(snap["items"]), news_status=snap["status"], digest=d, archive_html=page)
    except Exception as exc:  # noqa: BLE001 - the story never waits for news
        rec.update(status="absent", reason=f"news could not be read: {type(exc).__name__}: {exc}"[:500])
    if not persist:
        return rec
    try:
        _write(path, json.dumps(rec, ensure_ascii=False, indent=1))
    except OSError as exc:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return {"edition_id": rec["edition_id"], "revision": rec["revision"], "edition_date": rec["edition_date"],
                "status": "absent", "snapshot_id": rec.get("snapshot_id"),
                "reason": f"binding could not be saved ({type(exc).__name__}: {exc}); story only"[:500]}
    return rec


def site_files(binding: dict | None) -> dict[str, str]:
    """Site paths (under the allowed history/ prefix) for a bound brief's archive page."""
    if not binding or binding.get("status") != "bound" or not binding.get("archive_html"):
        return {}
    return {f"history/news/{binding['edition_date']}/index.html": binding["archive_html"]}

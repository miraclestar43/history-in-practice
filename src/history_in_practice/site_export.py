"""Export editions into a StarHub working copy and verify a live deployment.

Only paths under ALLOWED_PREFIXES are ever written; anything else (e.g.
articles.html, data/articles/) is refused. Verification never trusts HTTP 200
(starhub.vip returns 200 + the homepage for unknown paths): it requires JSON
content-type, parseable JSON, matching edition_id/revision/content_sha256 and
both languages present.
"""
from __future__ import annotations
import hashlib, json, shutil, urllib.request
from pathlib import Path
from . import render

ALLOWED_PREFIXES = ("history/", "data/history/")


class ExportError(RuntimeError):
    pass


def _safe_dest(root: Path, rel: str) -> Path:
    rel = rel.lstrip("/")
    if not rel.startswith(ALLOWED_PREFIXES) or ".." in Path(rel).parts:
        raise ExportError(f"refusing to write outside allowed paths: {rel}")
    return root / rel


def export(objs: list[dict], site_root: Path) -> list[str]:
    """Write history page + data into site_root (a website working copy). Returns written rel paths."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        render.build([dict(o) for o in objs], Path(td), "https://starhub.vip")
        written = []
        for f in sorted((Path(td) / "site").rglob("*")):
            if f.is_file():
                rel = f.relative_to(Path(td) / "site").as_posix()
                dest = _safe_dest(site_root, rel); dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dest); written.append(rel)
    return written


NOTICE_KINDS = ("under_revision",)


def preview(site_root: Path, samples: list[dict], notices: dict[str, dict] | None = None) -> list[str]:
    """Add reader samples (status "reader_sample", already re-verified as admitted by the caller) and dated notices to an
    existing TEST preview, keeping every item already listed. Existing edition JSON files are never rewritten: a notice is
    index metadata keyed to an edition *and revision* (a sent TEST keeps its bytes and hash). Returns written rel paths."""
    import tempfile
    ip = _safe_dest(site_root, "data/history/index.json")
    index = json.loads(ip.read_text(encoding="utf-8")) if ip.exists() else {"schema_version": "0.2", "items": []}
    for o in samples:
        if o.get("status") != "reader_sample" or not o.get("preview_date"):
            raise ExportError(f"{o.get('edition_id')}: not a sample object")
    written = []
    with tempfile.TemporaryDirectory() as td:
        render.build([dict(o) for o in samples], Path(td), "https://starhub.vip")
        new = json.loads((Path(td) / "site/data/history/index.json").read_text(encoding="utf-8"))["items"]
        for f in sorted((Path(td) / "site").rglob("*")):
            rel = f.relative_to(Path(td) / "site").as_posix()
            if f.is_file() and (rel.startswith("data/history/samples/") or rel == "history/index.html"):
                dest = _safe_dest(site_root, rel); dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dest); written.append(rel)
    ids = {x["edition_id"] for x in new}
    items = [x for x in index["items"] if x["edition_id"] not in ids] + new
    for eid, n in (notices or {}).items():
        it = next((x for x in items if x["edition_id"] == eid), None)
        if it is None:
            raise ExportError(f"notice for {eid}: not listed on this site")
        if n.get("kind") not in NOTICE_KINDS or not (n.get("zh") and n.get("en") and n.get("at")):
            raise ExportError(f"notice for {eid}: needs kind in {NOTICE_KINDS}, at, zh, en")
        if n.get("revision") != it["revision"]:
            raise ExportError(f"notice for {eid}: revision {n.get('revision')} != listed revision {it['revision']}")
        it["notice"] = {k: n[k] for k in ("kind", "at", "revision", "zh", "en")}
    items.sort(key=lambda x: x["edition_date"], reverse=True)
    ip.parent.mkdir(parents=True, exist_ok=True)
    ip.write_text(json.dumps({"schema_version": index.get("schema_version", "0.2"), "mode": "test", "items": items}, ensure_ascii=False, indent=1),
                  encoding="utf-8")                                 # the page shows its TEST banner only for this index
    return written + ["data/history/index.json"]


def http_fetch(url: str, timeout=20) -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "history-in-practice-verify/0.3", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read(5_000_000)
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", b""


def verify(obj: dict, base_url: str, fetch=http_fetch) -> tuple[bool, list[str]]:
    """Check the deployed index + edition JSON against the frozen local object."""
    problems = []
    st, ct, body = fetch(base_url.rstrip("/") + "/data/history/index.json")
    if st != 200 or "json" not in ct.lower():
        return False, [f"index: status {st}, content-type {ct!r} (site fallback or not deployed)"]
    try:
        idx = json.loads(body)
    except ValueError:
        return False, ["index: not parseable JSON"]
    item = next((i for i in idx.get("items", []) if i.get("edition_id") == obj["edition_id"]), None)
    if not item:
        return False, ["index: edition missing"]
    if item.get("revision") != obj["revision"]:
        problems.append(f"index: revision {item.get('revision')} != {obj['revision']}")
    st, ct, body = fetch(base_url.rstrip("/") + "/" + item["path"])
    if st != 200 or "json" not in ct.lower():
        return False, problems + [f"edition: status {st}, content-type {ct!r}"]
    try:
        live = json.loads(body)
    except ValueError:
        return False, problems + ["edition: not parseable JSON"]
    if live.get("revision") != obj["revision"]:
        problems.append(f"edition: revision {live.get('revision')} != {obj['revision']}")
    if live.get("content_sha256") != obj["content_sha256"]:
        problems.append("edition: content_sha256 differs from frozen local object")
    recomputed = hashlib.sha256(render.canonical(live).encode()).hexdigest() if all(k in live for k in ("sections", "reflection")) else None
    if recomputed != obj["content_sha256"]:
        problems.append("edition: recomputed content hash differs (body changed or truncated)")
    for lang in ("zh", "en"):
        if not live.get("title", {}).get(lang) or any(not p.get(lang) for s in live.get("sections", []) for p in s.get("paras", [])):
            problems.append(f"edition: language {lang} missing or incomplete")
    return (not problems), problems

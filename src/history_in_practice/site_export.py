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

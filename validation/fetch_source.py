"""Validation-only source fetcher (not the production pipeline).

Fetches one source document, extracts plain text, classifies the result and
caches it with provenance. Status ladder (per adapter + concrete document,
never per domain):

    unverified -> reachable -> extractable -> evidence_usable

and failure classes: challenge_page, http_error, wrong_url, site_fallback,
no_relevant_content, too_large, network_error.

Usage (library):  fetch(source_dict, cache_dir) -> result dict
Stdlib only. Bounded: 8 MB per response, 30 s timeout.
"""
from __future__ import annotations
import hashlib, html, json, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "history-in-practice-validation/0.1 (+https://github.com/miraclestar43/history-in-practice)"
MAX_BYTES = 8 * 1024 * 1024
CHALLENGE_MARKERS = ("Checking the security of your connection", "challenge-platform",
                     "Just a moment...", "cf-chl-", "Enable JavaScript and cookies to continue")

def _get(url: str) -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(MAX_BYTES + 1)
            return r.status, r.headers.get("Content-Type", ""), body
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", e.read(65536)

def _adapter_url(src: dict) -> str:
    a, ref = src["adapter"], src["ref"]
    if a == "wikisource_raw":          # ref = "zh:史記/卷007"
        lang, title = ref.split(":", 1)
        return f"https://{lang}.wikisource.org/w/index.php?title={urllib.parse.quote(title)}&action=raw"
    if a == "wikisource_render":       # transcluded (ProofreadPage) chapters
        lang, title = ref.split(":", 1)
        return f"https://{lang}.wikisource.org/w/index.php?title={urllib.parse.quote(title)}&action=render"
    if a == "archive_djvu":            # ref = archive.org identifier
        return f"https://archive.org/download/{ref}/{ref}_djvu.txt"
    if a == "html":
        return ref
    raise ValueError(a)

def _to_text(adapter: str, ctype: str, body: bytes) -> str:
    if adapter in ("html", "wikisource_render"):
        m = re.search(rb'charset=["\']?([\w-]+)', body[:2000])
        mc = re.search(r"charset=([\w-]+)", ctype or "")
        enc = m.group(1).decode() if m else (mc.group(1) if mc else "utf-8")
        if enc.lower() in ("gb2312", "gbk"): enc = "gb18030"
        t = body.decode(enc, errors="replace")
        t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
        t = re.sub(r"(?s)<[^>]+>", " ", t)
        return re.sub(r"[ \t\r\f\v]+", " ", html.unescape(t))
    t = body.decode("utf-8", errors="replace")
    if adapter == "wikisource_raw":
        t = re.sub(r"\{\{[^{}]*\}\}", "", t)          # simple templates
        t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
        t = re.sub(r"<ref[^>]*>.*?</ref>|<[^>]+>", "", t, flags=re.S)
    return t

def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s)

def locate(text: str, needle: str, context: int = 160) -> dict | None:
    """Exact match after whitespace normalisation (OCR line breaks)."""
    flat = _norm_ws(text)
    i = flat.find(_norm_ws(needle))
    if i < 0:
        return None
    return {"offset_in_normalised_text": i,
            "context": flat[max(0, i - context): i + len(_norm_ws(needle)) + context]}

def fetch(src: dict, cache_dir: Path) -> dict:
    url = _adapter_url(src)
    res = {"source_id": src["id"], "adapter": src["adapter"], "url": url,
           "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    t0 = time.monotonic()
    try:
        status, ctype, body = _get(url)
    except Exception as e:
        res.update(status="network_error", error=str(e)[:200]); return res
    res.update(http_status=status, content_type=ctype, bytes=len(body),
               seconds=round(time.monotonic() - t0, 2))
    if len(body) > MAX_BYTES:
        res["status"] = "too_large"; return res
    head = body[:6000].decode("utf-8", errors="ignore")
    if (status == 202 and len(body) == 0) or any(m in head for m in CHALLENGE_MARKERS):
        res["status"] = "challenge_page"; return res
    if status == 404:
        res["status"] = "wrong_url"; return res
    if status >= 400:
        res["status"] = "http_error"; return res
    text = _to_text(src["adapter"], ctype, body)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{src['id']}.txt").write_text(text, encoding="utf-8")
    res.update(text_sha256=sha, text_chars=len(text), cache_file=f"{src['id']}.txt")
    # relevance: every expected marker must occur (catches SPA/home fallbacks)
    markers = src.get("must_contain", [])
    missing = [m for m in markers if m not in _norm_ws(text)]
    if src.get("site_fallback_marker") and src["site_fallback_marker"] in text:
        res["status"] = "site_fallback"; return res
    res["status"] = "extractable" if missing else "evidence_usable"
    res["missing_markers"] = missing
    return res

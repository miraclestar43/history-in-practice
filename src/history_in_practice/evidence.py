"""Evidence packs: verbatim excerpts cut from cached source text by anchors.

Every excerpt is an exact span of the normalised cached text (CJK sources:
whitespace removed; Latin: collapsed), with its offset and the source text's
SHA-256, so a reviewer can find it again. Model memory is never evidence."""
from __future__ import annotations
import re
from pathlib import Path

CJK_ADAPTER_HINT = ("zh:",)


def clean(t: str) -> str:
    t = re.sub(r'<span>",\{"template.*?<pageseparator />"\]\}\'>', "", t)
    return t.replace("​", "")


def normalise(text: str, cjk: bool) -> str:
    text = clean(text)
    return re.sub(r"\s+", "", text) if cjk else re.sub(r"\s+", " ", text)


def dehyphen(s: str) -> str:
    return re.sub(r"(\w)- (\w)", r"\1\2", s)


def cut(text: str, start: str, end: str, max_len=2500):
    i = text.find(start)
    if i < 0:
        return None, "start anchor not found"
    j = text.find(end, i + len(start) - len(end))
    if j < 0 or j - i > max_len:
        return None, "end anchor not found within limit"
    return (i, text[i:j + len(end)]), None


def build(spec_rows, sources: dict, cache: Path) -> tuple[dict, list[str]]:
    """spec_rows: [[eid, source_id, start, end, locator]]; sources: {sid: fetch-result-with-ref}."""
    pack, errors = {"sources": {}, "excerpts": []}, []
    for eid, sid, a, b, loc in spec_rows:
        src = sources.get(sid)
        if not src or src.get("status") != "evidence_usable":
            errors.append(f"{eid}: source {sid} not evidence_usable ({src.get('status') if src else 'missing'})"); continue
        cjk = bool(src.get("cjk")) or str(src.get("ref", "")).startswith(CJK_ADAPTER_HINT) or sid.startswith(("A-", "C-QSJS", "C-YMTXL"))
        text = normalise((cache / f"{sid}.txt").read_text(encoding="utf-8"), cjk)
        res, err = cut(text, a, b)
        if err:
            errors.append(f"{eid}: {err}"); continue
        off, quote = res
        pack["sources"][sid] = {k: src.get(k) for k in ("title", "url", "ref", "basis", "status", "http_status", "fetched_at", "text_sha256")}
        pack["excerpts"].append({"id": eid, "source_id": sid, "locator": loc, "offset": off,
                                 "start_anchor_hits": text.count(a), "quote": quote, "display": dehyphen(quote)})
    return pack, errors


def spans(pack: dict, ids: list[str] | None = None) -> list[list]:
    """Canonical spans [[ref, start, end]] for the registry."""
    out = []
    for e in pack["excerpts"]:
        if ids and e["id"] not in ids:
            continue
        ref = pack["sources"][e["source_id"]].get("ref") or e["source_id"]
        out.append([ref, e["offset"], e["offset"] + len(e["quote"])])
    return out

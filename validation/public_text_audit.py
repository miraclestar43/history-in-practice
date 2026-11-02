"""Public-repository audit (2026-11-01): how much verbatim text of in-copyright books sits in files Git tracks.

The column quotes short passages; whole evidence packs, reading windows and run records must not make the public
repository a copy of a book. For every tracked text file, every string of 40+ characters is tested against the local
caches of the in-copyright books (config/books/library.json `rights`, default in copyright; 胡适口述自传 included):
a string counts when windows taken from it occur verbatim in a book. Reports, per file, the counted characters and the
longest such string. Reads only local files; prints JSON. Exit 1 when a file is over the limits.

  .venv/bin/python validation/public_text_audit.py [--limit-file 1500] [--limit-string 400]
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from history_in_practice.config import data_dir          # noqa: E402
from history_in_practice.evidence import normalise       # noqa: E402

EXTRA = {"S-BK-HUSHI": True}                             # 胡适口述自传 (唐德刚 译注), used before the library existed


def copyrighted_caches() -> dict[str, str]:
    lib = json.loads((REPO / "config/books/library.json").read_text(encoding="utf-8"))
    sids = {b.get("source_id") or f"S-{b['book_id']}": b.get("language", "zh") == "zh" for b in lib["books"]
            if b.get("rights") != "public_domain"} | EXTRA
    out = {}
    for sid, cjk in sids.items():
        p = data_dir() / "source_cache" / f"{sid}.txt"
        if p.exists():
            out[sid] = normalise(p.read_text(encoding="utf-8"), cjk)
    return out


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def from_book(s: str, caches: dict[str, str]) -> str | None:
    n = normalise(s, True)
    if len(n) < 40:
        return None
    probes = [n[i:i + 24] for i in (0, len(n) // 2 - 12, len(n) - 24)]
    for sid, text in caches.items():
        if sum(p in text for p in probes) >= 2:
            return sid
    return None


def audit(limit_file: int, limit_string: int) -> dict:
    caches = copyrighted_caches()
    files = subprocess.check_output(["git", "ls-files"], cwd=REPO, text=True).split("\n")
    rows = []
    for f in files:
        if not f.endswith((".json", ".jsonl", ".md", ".txt")) or f.startswith("src/"):
            continue
        raw = (REPO / f).read_text(encoding="utf-8", errors="replace")
        try:
            vals = list(strings(json.loads(raw))) if f.endswith(".json") else \
                [x for line in raw.splitlines() if line.strip() for x in strings(json.loads(line))] if f.endswith(".jsonl") else raw.split("\n\n")
        except ValueError:
            vals = raw.split("\n\n")
        hits = [(s, sid) for s in vals if (sid := from_book(s, caches))]
        if hits:
            n = sum(len(s) for s, _ in hits); longest = max(len(s) for s, _ in hits)
            rows.append({"file": f, "chars": n, "longest": longest, "sources": sorted({sid for _, sid in hits}),
                         "over": n > limit_file or longest > limit_string})
    rows.sort(key=lambda r: -r["chars"])
    return {"caches": sorted(caches), "limit_file": limit_file, "limit_string": limit_string, "files": rows,
            "over": [r["file"] for r in rows if r["over"]]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--limit-file", type=int, default=1500); ap.add_argument("--limit-string", type=int, default=400)
    a = ap.parse_args(); r = audit(a.limit_file, a.limit_string)
    print(json.dumps(r, ensure_ascii=False, indent=1)); sys.exit(1 if r["over"] else 0)

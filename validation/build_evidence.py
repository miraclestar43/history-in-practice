"""Build evidence packs from cached source text using start/end anchors.
Every quote is an exact span of the normalised cached text (CJK: whitespace
removed; Latin: whitespace collapsed). Records offset + source text hash."""
import json, re, sys
from pathlib import Path
root, cache = Path(sys.argv[1]), Path(sys.argv[2])
fetch = json.loads((root/"validation/fetch_results.json").read_text())
spec = json.loads((root/"validation/excerpt_spec.json").read_text())
def clean(t):  # drop ProofreadPage JSON residue left by the HTML stripper
    return re.sub(r'<span>",\{"template.*?<pageseparator />"\]\}\'>', '', t)
def norm(sid, t):
    t = clean(t).replace("\u200b", "")   # zero-width spaces from ProofreadPage markup
    return re.sub(r"\s+", "", t) if sid.startswith(("A-", "C-QSJS", "C-YMTXL")) else re.sub(r"\s+", " ", t)
def dehyphen(s): return re.sub(r"(\w)- (\w)", r"\1\2", s)
ok = True
for story, rows in spec.items():
    pack = {"story": story, "sources": {}, "excerpts": []}
    for eid, sid, a, b, loc in rows:
        t = norm(sid, (cache/f"{sid}.txt").read_text())
        n = t.count(a); i = t.find(a); j = t.find(b, i + len(a) - len(b) if i >= 0 else 0)
        if i < 0 or j < 0 or j - i > 2500:
            print(f"FAIL {eid}: start_hits={n} start={i} end={j}"); ok = False; continue
        quote = t[i:j+len(b)]
        f = fetch[sid]
        pack["sources"][sid] = {k: f.get(k) for k in ("title","url","basis","status","http_status","fetched_at","text_sha256")}
        pack["excerpts"].append({"id": eid, "source_id": sid, "locator": loc, "offset": i,
                                 "start_anchor_hits": n, "quote": quote, "display": dehyphen(quote)})
        print(f"ok   {eid:<6} {sid:<12} chars={len(quote):<5} anchor_hits={n}")
    out = root/"samples"/f"evidence_{story}.json"; out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(pack, ensure_ascii=False, indent=1))
sys.exit(0 if ok else 1)

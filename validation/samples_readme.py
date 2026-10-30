"""Generate samples/README.md tables from the article files and timing logs."""
import json, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import render, checks
ROOT = Path(__file__).resolve().parents[1]
CAT = {"china_ancient": "中国古代", "world": "世界史", "china_modern": "中国近现代", "us": "美国史"}

def timings(files):
    out = []
    for f in files:
        p = ROOT / f
        if p.exists():
            out += json.loads(p.read_text())
    return out

def main():
    t1 = timings(["samples/model_timings.json"]); t2 = timings(["samples/model_timings_v2.json"]); t3 = timings(["samples/model_timings_v3.json"])
    rows, trows = [], []
    for s in "ABCD":
        o = json.loads((ROOT / f"samples/{s}/article.json").read_text()); render.finalize(o)
        ev = json.loads((ROOT / f"samples/evidence_{s}.json").read_text())
        f, _ = checks.check(o, ev)
        edits = json.loads((ROOT / f"samples/{s}/editor_log_v2.json").read_text()) if (ROOT / f"samples/{s}/editor_log_v2.json").exists() else []
        html = (ROOT / f"samples/preview/email/{o['edition_id']}.html")
        bases = sorted({x.get("basis") for x in o["sources"] if x.get("basis") and not str(x.get("basis")).endswith("-derived")})
        rows.append(f"| [{s}]({s}/article.zh.md) · [EN]({s}/article.en.md) | {CAT[o['category']]} | {o['title']['zh']} | {o['reflection']['type']} | "
                    f"{o['length']['zh_chars']} 字 · 约 {o['reading_minutes']['zh']} 分钟 | {o['length']['en_words']} words · ~{o['reading_minutes']['en']} min | "
                    f"{len(ev['excerpts'])} / {len(bases)} | {html.stat().st_size // 1024 if html.exists() else '-'} KB | "
                    f"{sum(1 for l, _ in f if l == 'BLOCK')} | {max(0, len(edits) - 1)} |")
        def tot(t): return round(sum(x["wall_s"] for x in t if x.get("story") == s))
        steps = [x for x in t2 + t3 if x.get("story") == s]
        trows.append(f"| {s} | {tot(t1)} s | " + " · ".join(f"{x['step']} {x['wall_s']:.0f}s ({x['prompt_bytes']//1024}→{x['out_bytes']//1024} KB{'' if x.get('json_ok') else ', invalid JSON'})" for x in steps) + f" | {tot(t2) + tot(t3)} s |")
    return rows, trows

if __name__ == "__main__":
    r, t = main(); print("\n".join(r)); print(); print("\n".join(t))

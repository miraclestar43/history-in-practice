"""Finalize samples: recompute length/hash, write Markdown, render previews (fictional recipients)."""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from history_in_practice import render
for s in "ABCD":
    p = ROOT / f"samples/{s}/article.json"; o = json.loads(p.read_text()); render.finalize(o)
    p.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / f"samples/{s}/article.zh.md").write_text(render.markdown(o, "zh"), encoding="utf-8")
    (ROOT / f"samples/{s}/article.en.md").write_text(render.markdown(o, "en"), encoding="utf-8")
r = subprocess.run([str(ROOT / "bin/hip"), "render", *[str(ROOT / f"samples/{s}/article.json") for s in "ABCD"], "--out", str(ROOT / "samples/preview")],
                   capture_output=True, text=True)
print(r.stdout, r.stderr[-500:])

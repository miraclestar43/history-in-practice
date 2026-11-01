"""Manual editor pass on an automated draft: apply logged edits, re-finalize, re-check,
copy the result into samples/auto/<candidate>/ (git). The result is NOT admissible by
itself: `hip rereview EDITION --article FILE` binds a fresh review + parity check to it.
usage: editor_pass.py <draft_dir> <edits.json>"""
import json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(Path(__file__).parent))
from history_in_practice import render, checks
from assemble_v2 import ref

def main(draft_dir, edits_file):
    d = Path(draft_dir); o = json.loads((d / "article.json").read_text()); spec = json.loads(Path(edits_file).read_text()); log = []
    for e in spec["edits"]:
        r, k = ref(o, e["path"]); before = r[k]
        if "find" in e:
            assert before.count(e["find"]) == 1, (e["path"], e["find"][:40], before.count(e["find"]))
            r[k] = before.replace(e["find"], e["replace"])
        else:
            r[k] = e["new"]
        log.append({"path": e["path"], "before": before, "after": r[k], "reason": e["reason"]})
    o["revision"] = 1; o["status"] = "edited-manually"; render.finalize(o)      # not admissible by itself: see below
    ev = json.loads((d / "evidence.json").read_text()); f, st = checks.check(o, ev)
    out = ROOT / "samples/auto" / d.name; out.mkdir(parents=True, exist_ok=True)
    (out / "article.json").write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "evidence.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "editor_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copy(Path(edits_file), out / "edits.json")
    for name in ("draft_zh.json", "review_zh.json", "en.json", "report.json"):
        if (d / name).exists(): shutil.copy(d / name, out / ("model_" + name))
    (out / "article.zh.md").write_text(render.markdown(o, "zh"), encoding="utf-8"); (out / "article.en.md").write_text(render.markdown(o, "en"), encoding="utf-8")
    blocking = [x for x in f if x[0] in ("BLOCK", "FIX")]
    print(json.dumps({"edits": len(log), "length": o["length"], "minutes": o["reading_minutes"], "blocking": blocking,
                      "next": ("fix the BLOCK/FIX findings first" if blocking else
                               f"bin/hip rereview {o['edition_id']} --article {out / 'article.json'}  (fresh review + parity bound to this file; admits only if clean)")},
                     ensure_ascii=False))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

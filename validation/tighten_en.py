"""Stage-3: tighten the (editor-corrected) English of samples/<S>/article.json
toward ~10 minutes. Writes samples/<S>/model_runs/7_en_tight.json + metrics."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from draft_pipeline import step, ROOT, P

def en_view(o):
    return {"title": o["title"]["en"], "dek": o["dek"]["en"],
            "sections": [{"id": s["id"], "heading": s["heading"]["en"], "paras": [{"t": p["en"], "kind": p["kind"], "ev": p["ev"]} for p in s["paras"]]} for s in o["sections"]],
            "reflection": {"type": o["reflection"]["type"], "scenario": o["reflection"]["scenario"]["en"], "question": o["reflection"]["question"]["en"],
                           "example": {k: o["reflection"]["example"][k]["en"] for k in ("assumptions", "steps", "alternative")}},
            "uncertainty_note": o["uncertainty_note"]["en"]}

def zh_text(o):
    return "\n".join(p["zh"] for s in o["sections"] for p in s["paras"])

if __name__ == "__main__":
    out = ROOT / "samples/model_timings_v3.json"; allm = json.loads(out.read_text()) if out.exists() else []
    for s in sys.argv[1:]:
        o = json.loads((ROOT / f"samples/{s}/article.json").read_text())
        prompt = f"{(P/'tighten_en.md').read_text()}\n\n<english>\n{json.dumps(en_view(o), ensure_ascii=False)}\n</english>\n\n<chinese>\n{zh_text(o)}\n</chinese>"
        obj, m = step(s, "7_en_tight", prompt, ROOT / f"samples/{s}/model_runs", 2100)
        allm.append(m); out.write_text(json.dumps(allm, ensure_ascii=False, indent=1))

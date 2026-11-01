"""Sample-drafting pipeline: 3 isolated Hermes calls per story, sequential.
Writes raw outputs + metrics to samples/<story>/model_runs/. Validation only."""
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import run_hermes

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "validation/prompts"
def evidence_block(story):
    pack = json.loads((ROOT/f"samples/evidence_{story}.json").read_text())
    lines = []
    for e in pack["excerpts"]:
        src = pack["sources"][e["source_id"]]["title"]
        lines.append(f"[{e['id']}] 来源：{src}；位置：{e['locator']}\n{e['display']}")
    return "<evidence>\n" + "\n\n".join(lines) + "\n</evidence>"

def parse_json(text):
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1].rsplit("```", 1)[0]
    i, j = s.find("{"), s.rfind("}")
    try:
        return json.loads(s[i:j+1])
    except ValueError:
        import re
        return json.loads(re.sub(r",\s*([\]}])", r"\1", s[i:j+1]))   # trailing-comma slip

def step(story, name, prompt, outdir, timeout_s):
    r = run_hermes.call(prompt, timeout_s=timeout_s)
    meta = {k: v for k, v in r.items() if k != "text"}
    meta.update(step=name, story=story, finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    (outdir/f"{name}.raw.txt").write_text(r["text"], encoding="utf-8")
    try:
        obj = parse_json(r["text"]); meta["json_ok"] = True
        (outdir/f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        obj = None; meta["json_ok"] = False; meta["json_error"] = str(e)[:200]
    print(json.dumps(meta, ensure_ascii=False), flush=True)
    return obj, meta

def run(story):
    outdir = ROOT/f"samples/{story}/model_runs"; outdir.mkdir(parents=True, exist_ok=True)
    brief = (ROOT/f"samples/briefs/{story}.md").read_text()
    ev = evidence_block(story); style = (P/"style_zh.md").read_text()
    metrics = []
    draft_prompt = f"{style}\n\n{(P/'draft_zh.md').read_text()}\n\n【编辑简报】\n{brief}\n\n【证据包】\n{ev}"
    draft, m = step(story, "1_draft_zh", draft_prompt, outdir, 900); metrics.append(m)
    if draft is None:  # one bounded repair attempt
        draft, m = step(story, "1b_draft_zh_retry", draft_prompt + "\n\n[上一次输出不是合法 JSON。只输出一个合法 JSON 对象。]", outdir, 900); metrics.append(m)
    if draft is None:
        return metrics
    review_prompt = f"{(P/'review_zh.md').read_text()}\n\n【证据包】\n{ev}\n\n【稿件】\n{json.dumps(draft, ensure_ascii=False)}"
    _, m = step(story, "2_review_zh", review_prompt, outdir, 600); metrics.append(m)
    en_prompt = f"{(P/'translate_en.md').read_text()}\n\n<evidence>\n{ev}\n</evidence>\n\n<article_zh>\n{json.dumps(draft, ensure_ascii=False)}\n</article_zh>"
    _, m = step(story, "3_en", en_prompt, outdir, 900); metrics.append(m)
    return metrics

if __name__ == "__main__":
    allm = []
    t0 = time.monotonic()
    for s in sys.argv[1:]:
        allm += run(s)
    out = ROOT/"samples/model_timings.json"
    prev = json.loads(out.read_text()) if out.exists() else []
    out.write_text(json.dumps(prev + allm, ensure_ascii=False, indent=1))
    print("TOTAL_WALL_S", round(time.monotonic() - t0, 1))

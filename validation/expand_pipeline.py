"""Stage-2 sample pipeline (single-language ten-minute target): expand the
edited stage-1 article with new evidence, review it, and write a natural
English edition. Isolated Hermes runner, sequential. Validation only."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from draft_pipeline import evidence_block, step, ROOT, P

TIMEOUTS = {"4_expand_zh": 1800, "5_review_zh": 1200, "6_en_long": 2100}

def current_zh(story):
    o = json.loads((ROOT / f"samples/{story}/article.json").read_text())
    return {"title": o["title"]["zh"], "dek": o["dek"]["zh"],
            "sections": [{"id": s["id"], "heading": s["heading"]["zh"],
                          "paras": [{"t": p["zh"], "kind": p["kind"], "ev": p["ev"]} for p in s["paras"]]} for s in o["sections"]],
            "reflection": {"type": o["reflection"]["type"], "scenario": o["reflection"]["scenario"]["zh"],
                           "question": o["reflection"]["question"]["zh"],
                           "example": {k: o["reflection"]["example"][k]["zh"] for k in ("assumptions", "steps", "alternative")}},
            "uncertainty_note": o["uncertainty_note"]["zh"]}

def run(story):
    out = ROOT / f"samples/{story}/model_runs"; out.mkdir(parents=True, exist_ok=True)
    ev = evidence_block(story); style = (P / "style_zh.md").read_text()
    brief = (ROOT / f"samples/briefs_v2/{story}.md").read_text()
    cur = json.dumps(current_zh(story), ensure_ascii=False)
    ms = []
    prompt = f"{style}\n\n{(P/'expand_zh.md').read_text()}\n\n【扩展简报】\n{brief}\n\n【证据包】\n{ev}\n\n【现有中文稿】\n{cur}"
    zh, m = step(story, "4_expand_zh", prompt, out, TIMEOUTS["4_expand_zh"]); ms.append(m)
    if zh is None:
        zh, m = step(story, "4b_expand_zh_retry", prompt + "\n\n[上一次输出不是合法 JSON。只输出一个合法 JSON 对象。]", out, TIMEOUTS["4_expand_zh"]); ms.append(m)
    if zh is None:
        return ms
    rv = f"{(P/'review_zh.md').read_text()}\n\n【证据包】\n{ev}\n\n【稿件】\n{json.dumps(zh, ensure_ascii=False)}"
    _, m = step(story, "5_review_zh", rv, out, TIMEOUTS["5_review_zh"]); ms.append(m)
    en = f"{(P/'translate_en_long.md').read_text()}\n\n<evidence>\n{ev}\n</evidence>\n\n<article_zh>\n{json.dumps(zh, ensure_ascii=False)}\n</article_zh>"
    e, m = step(story, "6_en_long", en, out, TIMEOUTS["6_en_long"]); ms.append(m)
    if e is None:
        _, m = step(story, "6b_en_long_retry", en + "\n\n[Your previous reply was not valid JSON. Reply with one valid JSON object only.]", out, TIMEOUTS["6_en_long"]); ms.append(m)
    return ms

if __name__ == "__main__":
    t0 = time.monotonic(); allm = []
    outp = ROOT / "samples/model_timings_v2.json"
    for s in sys.argv[1:]:
        allm += run(s)
        outp.write_text(json.dumps(allm, ensure_ascii=False, indent=1))   # checkpoint after each story
    print("TOTAL_WALL_S", round(time.monotonic() - t0, 1))

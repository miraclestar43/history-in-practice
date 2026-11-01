"""Merge Hermes zh + en drafts into one bilingual object, then apply the
editor's explicit edits (samples/<S>/edits.json). Every edit is logged with
before/after/reason in samples/<S>/editor_log.json (internal, not public).

edits.json: {"meta": {...top-level fields to set...},
             "edits": [{"path": "sections.story.1.zh", "new": "...", "reason": "..."}],
             "replace_section": {"today": [{"zh":..,"en":..,"kind":..,"ev":[..]}]} }
path forms: title.zh | dek.en | sections.<id>.<i>.<zh|en|kind|ev> |
            sections.<id>.heading.<zh|en> | reflection.<k>.<zh|en> |
            reflection.example.<k>.<zh|en> | uncertainty_note.<zh|en>"""
import copy, json, sys
from pathlib import Path

def merge(zh, en):
    o = {"title": {"zh": zh["title"], "en": en["title"]}, "dek": {"zh": zh["dek"], "en": en["dek"]}, "sections": []}
    ens = {s["id"]: s for s in en["sections"]}
    for s in zh["sections"]:
        e = ens.get(s["id"], {"heading": "", "paras": []})
        paras = []
        for i, p in enumerate(s["paras"]):
            pe = e["paras"][i] if i < len(e["paras"]) else {"t": ""}
            paras.append({"zh": p["t"], "en": pe.get("t", ""), "kind": p["kind"], "ev": p.get("ev", [])})
        o["sections"].append({"id": s["id"], "heading": {"zh": s["heading"], "en": e.get("heading", "")}, "paras": paras})
    rz, re_ = zh["reflection"], en["reflection"]
    o["reflection"] = {"type": rz["type"], **{k: {"zh": rz[k], "en": re_.get(k, "")} for k in ("scenario", "question")},
                       "example": {k: {"zh": rz["example"][k], "en": re_.get("example", {}).get(k, "")} for k in ("assumptions", "steps", "alternative")}}
    o["uncertainty_note"] = {"zh": zh["uncertainty_note"], "en": en.get("uncertainty_note", "")}
    return o

def get_ref(o, path):
    parts = path.split("."); cur = o
    if parts[0] == "sections":
        sec = next(s for s in cur["sections"] if s["id"] == parts[1])
        if parts[2] == "heading": return sec["heading"], parts[3]
        return sec["paras"][int(parts[2])], parts[3]
    for k in parts[:-1]: cur = cur[k]
    return cur, parts[-1]

def main(story):
    d = Path(f"samples/{story}"); runs = d / "model_runs"
    zh = json.loads((runs / "1_draft_zh.json").read_text()); en = json.loads((runs / "3_en.json").read_text())
    o = merge(zh, en); spec = json.loads((d / "edits.json").read_text()); log = []
    for sid, paras in spec.get("replace_section", {}).items():
        sec = next(s for s in o["sections"] if s["id"] == sid)
        log.append({"path": f"sections.{sid}", "before": copy.deepcopy(sec["paras"]), "after": paras, "reason": spec.get("replace_reason", {}).get(sid, "")})
        sec["paras"] = paras
    for ed in spec["edits"]:
        ref, key = get_ref(o, ed["path"]); before = ref.get(key)
        ref[key] = ed["new"]; log.append({"path": ed["path"], "before": before, "after": ed["new"], "reason": ed["reason"]})
    o.update(spec["meta"])
    order = ["schema_version", "edition_id", "episode_id", "status", "edition_date", "category", "revision", "title", "dek", "preheader",
             "sections", "reflection", "uncertainty_note", "sources", "further_reading", "single_basis_disclosed", "correction_note"]
    o = {k: o[k] for k in order if k in o} | {k: v for k, v in o.items() if k not in order}
    (d / "article.json").write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "editor_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{story}: {len(log)} editor changes")

if __name__ == "__main__":
    main(sys.argv[1])

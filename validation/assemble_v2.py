"""Stage-2 assembly: merge 4_expand_zh + 6_en_long (or 7_en_tight if present)
and apply the editor's exact find/replace edits from samples/<S>/edits_v2.json.
Each edit must match exactly once; every change is logged with its reason."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice.pipeline import merge

def ref(o, path):
    parts = path.split(".")
    if parts[0] == "sections":
        sec = next(s for s in o["sections"] if s["id"] == parts[1])
        return (sec["heading"], parts[3]) if parts[2] == "heading" else (sec["paras"][int(parts[2])], parts[3])
    cur = o
    for k in parts[:-1]: cur = cur[k]
    return cur, parts[-1]

def main(story):
    d = Path(f"samples/{story}"); runs = d / "model_runs"
    zh = json.loads((runs / "4_expand_zh.json").read_text())
    en_file = runs / ("7_en_tight.json" if (runs / "7_en_tight.json").exists() else "6_en_long.json")
    o = merge(zh, json.loads(en_file.read_text()))
    spec = json.loads((d / "edits_v2.json").read_text()); log = [{"base_en": en_file.name}]
    tightened = en_file.name.startswith("7_")
    for e in spec["edits"]:
        if tightened and e["path"].endswith(".en"):
            continue        # already applied to the English that was fed to the tightening step
        r, k = ref(o, e["path"]); before = r[k]
        if "find" in e:
            n = before.count(e["find"])
            if n != 1:
                raise SystemExit(f"{story}: edit {e['path']} find matched {n} times: {e['find'][:40]!r}")
            r[k] = before.replace(e["find"], e["replace"])
        else:
            r[k] = e["new"]
        log.append({"path": e["path"], "before": before, "after": r[k], "reason": e["reason"]})
    if spec.get("translated_quote_marks"):
        # English-source story: 「」 is reserved for verbatim Chinese; translations use “”
        def fix(s): return s.replace("「", "“").replace("」", "”")
        for s in o["sections"]:
            for p_ in s["paras"]: p_["zh"] = fix(p_["zh"])
        for k in ("scenario", "question"): o["reflection"][k]["zh"] = fix(o["reflection"][k]["zh"])
        for k in o["reflection"]["example"]: o["reflection"]["example"][k]["zh"] = fix(o["reflection"]["example"][k]["zh"])
        o["uncertainty_note"]["zh"] = fix(o["uncertainty_note"]["zh"]); o["dek"]["zh"] = fix(o["dek"]["zh"])
    old = json.loads((d / "article.json").read_text())
    meta = {k: old[k] for k in ("schema_version", "edition_id", "episode_id", "status", "edition_date", "category", "revision",
                                "preheader", "sources", "further_reading", "single_basis_disclosed", "correction_note") if k in old}
    meta["revision"] = 2; meta.update(spec.get("meta", {}))
    o = meta | o
    (d / "article.json").write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "editor_log_v2.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{story}: {len(log)-1} editor changes on stage-2 drafts (English base: {en_file.name})")

if __name__ == "__main__":
    main(sys.argv[1])

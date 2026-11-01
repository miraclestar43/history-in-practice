"""Per-edition final-editor metrics for the report, computed from the committed records (samples/auto/<cid>/final/).
usage: .venv/bin/python validation/final_edit_stats.py [--markdown]"""
import collections, glob, json, sqlite3, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DB = sqlite3.connect(ROOT / "data/hip.sqlite")

rows = []
for d in sorted(glob.glob(str(ROOT / "samples/auto/*/final"))):
    recs = sorted(glob.glob(f"{d}/attempt-*_final_editor_record.json"), key=lambda p: int(p.split("attempt-")[1].split("_")[0]))
    if not recs:
        continue
    att = [json.loads(Path(p).read_text()) for p in recs]
    last = att[-1]
    issues = [(k, i) for k, r in enumerate(att) for i in r["issues"] if i.get("severity") in ("fix", "block")]
    disp = collections.Counter(i.get("disposition") or ("carried to next attempt" if k < len(att) - 1 else
                               "closed by checker fix" if i.get("origin") == "checker" else "open") for k, i in issues)
    cats = collections.Counter(i.get("category") for r in att for i in r["issues"] if i.get("severity") in ("fix", "block") and i.get("origin") == "final-editor audit")
    calls = [c for r in att for c in r["calls"]]
    st = DB.execute("SELECT status, COALESCE(approval,'') FROM edition WHERE edition_id=?", (Path(d).parent.name,)).fetchone() or ("?", "")
    rows.append({"edition": Path(d).parent.name, "attempts": len(att), "outcome": last["outcome"], "status": st[0],
                 "elapsed_min": round(sum(r["elapsed_min"] for r in att), 1), "calls": len(calls),
                 "retries": sum(1 for c in calls if c["attempt"] > 1),
                 "output_tokens_k": round(sum((c["tokens"] or {}).get("output_tokens") or 0 for c in calls) / 1000, 1),
                 "inherited_mimo": len(att[0]["inherited"]), "contamination_lines": len(att[0]["contamination"]),
                 "issues_fix_block": len(issues), "dispositions": dict(disp), "audit_categories": dict(cats.most_common(5)),
                 "edits": sum(len(r["edits"]) for r in att),
                 "verify_trajectory": [len([i for i in (x.get("verify") or {}).get("issues", []) if i.get("severity") in ("fix", "block")])
                                       for r in att for x in r["rounds"]],
                 "editor": f"{last['editor']['name']} / {last['editor'].get('model_reported') or last['editor']['model']} / CLI {last['editor']['cli_version'].split()[0]}"})

if "--markdown" in sys.argv:
    print("| Edition | Attempts | Minutes | Calls | Out tokens (k) | MiMo issues inherited | Fix/block issues | Fixed / rejected / dup / open | Edits | Verify fix/block per round | Status |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        d = r["dispositions"]
        print(f"| {r['edition'].replace('cand-', '')} | {r['attempts']} | {r['elapsed_min']} | {r['calls']} | {r['output_tokens_k']} | {r['inherited_mimo']} | "
              f"{r['issues_fix_block']} | {d.get('fixed', 0)} / {d.get('rejected', 0)} / {d.get('duplicate', 0)} / {d.get('open', 0)}"
              f"{' (+' + str(d['closed by checker fix']) + ' checker)' if d.get('closed by checker fix') else ''} | {r['edits']} | "
              f"{' → '.join(map(str, r['verify_trajectory']))} | {'admitted' if r['status'] == 'checked' else r['status']} |")
else:
    print(json.dumps(rows, ensure_ascii=False, indent=1))

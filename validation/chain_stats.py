"""Per-candidate chain metrics for the stabilisation report (computed from logs, not typed):
supply proposal -> pipeline (draft/review/English) -> editor attempts (edit rounds, re-review, parity) -> outcome.
usage: chain_stats.py [CANDIDATE_ID ...]   (default: every candidate that has editor attempts)"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def calls(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def summary(cid: str) -> dict:
    sup = [a for a in calls(DATA / "supply/attempts.jsonl") if a.get("candidate_id") == cid]
    pipe = calls(DATA / "drafts" / cid / "calls.jsonl")
    att = []
    for w in sorted((DATA / "editor" / cid).glob("attempt-*"), key=lambda p: int(p.name.split("-")[1])):
        rec = json.loads((w / "editor_record.json").read_text()) if (w / "editor_record.json").exists() else {}
        cs = calls(w / "calls.jsonl")
        rounds = rec.get("rounds", []); traj = []
        for k, r in enumerate(rounds):
            nxt = len(rounds[k + 1]["issues_in"]) if k + 1 < len(rounds) else len(rec.get("remaining", []))
            carried = len(r.get("carried_over", []))
            traj.append({"round": r["round"], "in": len(r.get("issues_in", [])), "edits": len(r.get("edits_applied", [])),
                         "carried_unfixed": carried, "fresh_from_review": max(0, nxt - carried),
                         "review_refused": r.get("review_after") is None and r["round"] > 0})
        att.append({"attempt": w.name, "outcome": rec.get("outcome", "unfinished"), "trajectory": traj, "rounds": [r["round"] for r in rec.get("rounds", [])],
                    "issues_in": [len(r.get("issues_in", [])) for r in rec.get("rounds", [])],
                    "edits_applied": rec.get("edits_total"), "edits_failed": sum(len(r.get("edits_failed", [])) for r in rec.get("rounds", [])),
                    "remaining": len(rec.get("remaining", [])), "calls": len(cs), "invalid_json": sum(1 for c in cs if not c.get("json_ok")),
                    "model_min": round(sum(c.get("wall_s", 0) for c in cs) / 60, 1)})
    return {"candidate": cid,
            "supply": [{"min": round(a["call"]["wall_s"] / 60, 1), "proposed": a.get("proposed"), "kept": a.get("kept"), "outcome": a["outcome"]} for a in sup],
            "pipeline": {"calls": len(pipe), "invalid_json": sum(1 for c in pipe if c.get("json_ok") is False), "model_min": round(sum(c.get("wall_s", 0) for c in pipe) / 60, 1)},
            "editor": att,
            "model_min_total": round(sum(a["call"]["wall_s"] for a in sup) / 60 + sum(c.get("wall_s", 0) for c in pipe) / 60 + sum(x["model_min"] for x in att), 1)}


if __name__ == "__main__":
    ids = sys.argv[1:] or sorted(p.name for p in (DATA / "editor").iterdir() if p.is_dir())
    rows = [summary(c) for c in ids]
    print(json.dumps(rows, ensure_ascii=False, indent=1))
    attempts = [a for r in rows for a in r["supply"]]
    print(f"\nsupply attempts: {len(calls(DATA / 'supply/attempts.jsonl'))} total, outcomes "
          f"{json.dumps({o: sum(1 for a in calls(DATA / 'supply/attempts.jsonl') if a['outcome'] == o) for o in ('candidate', 'rejected')})}")

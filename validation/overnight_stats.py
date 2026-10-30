"""Model-call statistics for the overnight report (computed, not typed)."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def load(p):
    p = ROOT / p
    return json.loads(p.read_text()) if p.exists() else []

groups = {"stage 1 (short samples)": load("samples/model_timings.json"),
          "stage 2 (ten-minute expansion)": load("samples/model_timings_v2.json"),
          "stage 3 (English tightening)": load("samples/model_timings_v3.json")}
auto = []
for r in sorted((ROOT / "data/drafts").glob("*/calls.jsonl")):
    for line in r.read_text().splitlines():
        if line.strip():
            auto.append(json.loads(line))
groups["automated candidates"] = auto
tot_calls = tot_wall = 0
for name, calls in groups.items():
    wall = sum(c.get("wall_s", 0) for c in calls); tot_calls += len(calls); tot_wall += wall
    bad = sum(1 for c in calls if not c.get("json_ok")); ref = sum(1 for c in calls if c.get("provider_refusal"))
    stalled = sum(1 for c in calls if c.get("rc") not in (0, None) or c.get("killed"))
    longest = max((c.get("wall_s", 0) for c in calls), default=0)
    print(f"{name}: {len(calls)} calls, {wall:.0f} s total, longest {longest:.0f} s, invalid/no JSON {bad} (refusals {ref}, killed/stopped {stalled})")
print(f"ALL: {tot_calls} model calls, {tot_wall/60:.1f} min of model time")

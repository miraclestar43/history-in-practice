import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from fetch_source import fetch
root = Path(sys.argv[1]); cache = Path(sys.argv[2])
man = json.loads((root / "validation/sources_manifest.json").read_text())
out = {}
for story, srcs in man["stories"].items():
    for s in srcs:
        r = fetch(s, cache); r["title"] = s["title"]; r["basis"] = s.get("basis"); r["story"] = story
        out[s["id"]] = r
        print(f"{s['id']:<13} {r['status']:<20} http={r.get('http_status')} chars={r.get('text_chars','-')} missing={r.get('missing_markers','-')}")
        time.sleep(1.0)
(root / "validation/fetch_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

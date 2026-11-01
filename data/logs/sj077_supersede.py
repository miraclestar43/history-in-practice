"""Owner request 2026-10-31: a new Chinese story from an existing evidence pack (sj077-1's expanded pack), drafted under
the reader-first prompts. sj077-1 (pending, old prompts) is superseded, not deleted: its episode reservation is released
before the new draft reserves the same passage; on success its edition becomes `rejected` with the reason, on failure the
reservation is restored."""
import sys
sys.path.insert(0, "src")
from history_in_practice import cli, registry, state
d = cli.db(); OLD = "cand-auto-20261030-sj077-1"; NEW = "cand-auto-20261031-sj077-2"
step = sys.argv[1]
if step == "release":
    registry.set_status(d, f"ep-{OLD}", "superseded"); d.commit(); print("released", OLD)
elif step == "restore":
    registry.set_status(d, f"ep-{OLD}", "prepared"); d.commit(); print("restored", OLD)
elif step == "retire":
    state.transition(d, OLD, "rejected", note=f"superseded by {NEW}: redraft from the same evidence pack under the reader-first "
                     "prompts (owner request 2026-10-31); all drafts, editor and final-editor records kept",
                     reason=f"superseded by {NEW} (redraft under reader-first prompts)")
    d.commit(); print("retired", OLD, state.get(d, OLD)["status"])

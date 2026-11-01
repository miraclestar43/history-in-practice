"""Owner decision 2026-11-01: Claude (writer.py -> claude_cli) drafts, writes the English and edits; MiMo/Hermes left the main
chain. If Claude is unavailable nothing is drafted by another model -- the run stops with a health result -- and every
label comes from what the CLI reported, not from a configured name."""
import json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src")); sys.path.insert(0, str(Path(__file__).parent))
from history_in_practice import writer, llm, pipeline, supply, state, registry, claude_cli
from test_registry_pipeline import CANDIDATE, ALIASES


class Writer(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); os.environ["HIP_DATA_DIR"] = str(Path(self.td.name) / "data")
        self.db = state.connect(Path(self.td.name) / "s.sqlite"); registry.init(self.db, ALIASES)
        self.saved = writer.preflight, llm.call
        writer.preflight = lambda: ["not logged in (config X)"]
        def mimo(*a, **k):
            raise AssertionError("MiMo must never be called")
        llm.call = mimo

    def tearDown(self):
        writer.preflight, llm.call = self.saved
        os.environ.pop("HIP_DATA_DIR"); self.td.cleanup()

    def test_claude_unavailable_stops_prepare_and_supply_without_any_other_model(self):
        r = pipeline.prepare(CANDIDATE, self.db)
        self.assertEqual((r["outcome"], r.get("health")), ("not_run", True)); self.assertIn("writer unavailable (Claude)", r["reason"])
        self.assertIsNone(state.get(self.db, CANDIDATE["candidate_id"]))                 # nothing recorded as drafted
        entry = {"id": "X", "category": "china_ancient", "title": "t"}
        p = supply.propose(entry, self.db)
        self.assertEqual((p["outcome"], p.get("health")), ("not_run", True))

    def test_labels_come_from_the_cli_report(self):
        m = [{"meta": {"model": "claude-opus-5-5", "cli_version": "2.1.308", "apiKeySource": "none",
                       "modelUsage": {"claude-opus-5-5": {}}}}]
        lb = writer.label(m)
        self.assertEqual((lb["model"], lb["models_used"], lb["api_key_source"]), ("claude-opus-5-5", ["claude-opus-5-5"], "none"))
        self.assertEqual(writer.name(m), "Claude (claude-opus-5-5) via Claude Code CLI (claude.ai subscription)")
        self.assertIsNone(writer.label([{"meta": {}}])["model"])                         # nothing reported -> no invented name

    def test_real_cli_is_refused_under_unittest(self):
        r = claude_cli.call("hi")
        self.assertEqual(r["text"], ""); self.assertIn("refused under unittest", r["meta"]["error"])


if __name__ == "__main__":
    unittest.main()

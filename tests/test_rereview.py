import json, os, shutil, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src")); sys.path.insert(0, str(Path(__file__).parent))
from history_in_practice import state, registry, llm, render, cli, pipeline
from test_registry_pipeline import fake_call_factory
ROOT = Path(__file__).resolve().parents[1]


class Rereview(unittest.TestCase):
    """An edition admitted before records existed (approval NULL) is only schedulable after a fresh review of its exact content."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); os.environ["HIP_DATA_DIR"] = str(Path(self.td.name) / "data")
        self.auto = Path(self.td.name) / "auto" / "cand-x"; self.auto.mkdir(parents=True)
        o = json.loads((ROOT / "samples/D/article.json").read_text()); o["edition_id"] = "cand-x"; render.finalize(o)
        (self.auto / "article.json").write_text(json.dumps(o, ensure_ascii=False)); shutil.copy(ROOT / "samples/evidence_D.json", self.auto / "evidence.json")
        self.db = cli.db()
        state.transition(self.db, "cand-x", "prepared", category="us", path=str(self.auto / "article.json"))
        state.transition(self.db, "cand-x", "checked", content_sha256=o["content_sha256"])          # legacy: no approval
        self._call, self._repo = llm.call, cli.REPO
        cli.REPO = Path(self.td.name)                                                               # publish attempts into the temp tree

    def tearDown(self):
        llm.call = self._call; cli.REPO = self._repo; self.td.cleanup(); os.environ.pop("HIP_DATA_DIR")

    def run_rereview(self, review_issues):
        base = fake_call_factory()
        def call(prompt, timeout_s=0, **kw):
            r = base(prompt, timeout_s=timeout_s)
            if "事实审稿人" in prompt:
                r["text"] = json.dumps({"issues": review_issues, "overall": "x"}, ensure_ascii=False)
            return r
        llm.call = call
        a = type("A", (), {"edition": "cand-x", "rounds": 0, "article": None})()
        return cli.cmd_rereview(a)

    def test_clean_fresh_review_readmits_with_bound_approval(self):
        self.assertEqual(pipeline.inventory(self.db)["schedulable_total"], 0)
        self.assertEqual(self.run_rereview([]), 0)
        cur = state.get(self.db, "cand-x"); self.assertEqual((cur["status"], cur["approval"]), ("checked", "editor-record"))
        rec = json.loads((Path(self.td.name) / "samples/auto/cand-x/editor_record.json").read_text())
        self.assertEqual(rec["final_content_sha256"], cur["content_sha256"]); self.assertEqual(rec["edits_total"], 0)
        self.assertEqual(pipeline.inventory(self.db)["schedulable_total"], 1)

    def test_fresh_review_with_fix_keeps_it_pending(self):
        self.assertEqual(self.run_rereview([{"severity": "fix", "section": "hook", "para": 0, "problem": "年份不在证据里"}]), 2)
        cur = state.get(self.db, "cand-x"); self.assertEqual(cur["status"], "pending_review"); self.assertIn("editor:", cur["reason"])
        self.assertEqual(pipeline.inventory(self.db)["schedulable_total"], 0)


if __name__ == "__main__":
    unittest.main()

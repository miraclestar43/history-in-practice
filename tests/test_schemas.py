"""P1 (STABILIZATION_REVIEW §1): a parseable reply is not a review. Missing/mistyped `issues`, unknown severities and
the separate fact arrays must never let a draft through - in the pipeline, the editor stage, or a hand-made record."""
import copy, json, shutil, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src")); sys.path.insert(0, str(Path(__file__).parent))
from history_in_practice import registry, state, editor, schemas, pipeline, render
from test_registry_pipeline import CANDIDATE, ALIASES, fake_call_factory
ROOT = Path(__file__).resolve().parents[1]

BAD_SHAPES = {
    "empty object": {},
    "issues missing": {"overall": "fine"},
    "issues null": {"issues": None, "overall": "fine"},
    "issues a string": {"issues": "none", "overall": "fine"},
    "unknown severity": {"issues": [{"severity": "minor", "section": "hook", "para": 0, "problem": "p"}]},
    "issue without problem": {"issues": [{"severity": "fix", "section": "hook", "para": 0}]},
    "fact array not a list": {"issues": [], "unsupported_claims": "x"},
}
FACT_ONLY = {k: {"issues": [], k: ["证据包里没有这一句"], "overall": "ok"} for k in schemas.FACT_ARRAYS}


def model(review_reply):
    """Fake model whose every Chinese review returns `review_reply` (drafts, English, parity, edits stay valid)."""
    base = fake_call_factory()
    def call(prompt, timeout_s=0, **kw):
        r = base(prompt, timeout_s=timeout_s)
        if "事实审稿人" in prompt:
            r["text"] = json.dumps(review_reply, ensure_ascii=False)
        return r
    return call


class Shapes(unittest.TestCase):
    def test_bad_shapes_are_invalid(self):
        for name, obj in BAD_SHAPES.items():
            self.assertTrue(schemas.review(obj), name)
        self.assertTrue(schemas.parity({})); self.assertTrue(schemas.parity({"issues": [{"severity": "block", "path": "x", "problem": "p"}]}))
        self.assertTrue(schemas.edit({"edits": []}))                         # dispositions required
        self.assertTrue(schemas.draft_zh({"title": "t"}))

    def test_valid_empty_review_is_clean_and_fact_arrays_become_issues(self):
        self.assertEqual(schemas.review({"issues": [], "overall": "ok"}), [])
        self.assertEqual(schemas.review_issues({"issues": [], "overall": "ok"}), [])
        for k, obj in FACT_ONLY.items():
            self.assertEqual(schemas.review(obj), [], k)
            got = schemas.review_issues(obj)
            self.assertEqual(len(got), 1, k); self.assertEqual(got[0]["severity"], "fix"); self.assertIn(k, got[0]["problem"])

    def test_collect_issues_counts_fact_arrays(self):
        for k, obj in FACT_ONLY.items():
            self.assertEqual(len(editor.collect_issues(obj, {"issues": []}, [])), 1, k)


class Paths(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); self.cache = Path(self.td.name) / "cache"; self.cache.mkdir()
        shutil.copy(ROOT / "tests/fixtures/A-SJ56.txt", self.cache / "A-SJ56.txt")
        (self.cache / "A-SJ56.meta.json").write_text(json.dumps({"status": "evidence_usable", "source_id": "A-SJ56"}))
        self.db = state.connect(Path(self.td.name) / "s.sqlite"); registry.init(self.db, ALIASES)
        self.wd = Path(self.td.name) / CANDIDATE["candidate_id"]

    def tearDown(self):
        self.td.cleanup()

    def run_chain(self, review_reply):
        call = model(review_reply)
        r = pipeline.prepare(CANDIDATE, self.db, call=call, workdir=self.wd, cache=self.cache)
        rec = editor.edit(self.wd, call=call)
        a = editor.admit_with_record(self.db, self.wd / "edited.json", self.wd / "evidence.json", rec)
        return r, rec, a

    def test_invalid_reviews_never_admit_through_pipeline_and_editor(self):
        for name, bad in BAD_SHAPES.items():
            with self.subTest(name):
                self.tearDown(); self.setUp()
                r, rec, a = self.run_chain(bad)
                self.assertIn("review missing or invalid", r["reason"])          # pipeline: invalid initial review is not "clean"
                self.assertFalse(rec["final_reviewed"]); self.assertEqual(rec["outcome"], "pending_review")
                self.assertFalse(a["admitted"]); self.assertEqual(state.get(self.db, CANDIDATE["candidate_id"])["status"], "pending_review")
                calls = [json.loads(l) for l in (self.wd / "calls.jsonl").read_text().splitlines()]
                self.assertTrue(any(c.get("schema_ok") is False for c in calls))  # logged as a failed step, retried once

    def test_fact_array_only_findings_block_admission(self):
        for k, obj in FACT_ONLY.items():
            with self.subTest(k):
                self.tearDown(); self.setUp()
                r, rec, a = self.run_chain(obj)
                self.assertIn("review issues rated fix/block", r["reason"])
                self.assertEqual(rec["outcome"], "pending_review"); self.assertTrue(any(k in i["problem"] for i in rec["remaining"]))
                self.assertFalse(a["admitted"])

    def test_clean_valid_review_still_admits(self):
        r, rec, a = self.run_chain({"issues": [], "overall": "ok"})
        self.assertEqual(rec["outcome"], "admissible"); self.assertTrue(a["admitted"], a)
        last = rec["rounds"][-1]
        self.assertEqual(last["review_after"]["_schema"], schemas.REVIEW_SCHEMA); self.assertEqual(last["parity_after"]["_schema"], schemas.PARITY_SCHEMA)

    def hand_record(self):
        """A record made clean by the editor, for tampering below (the manual-record path)."""
        call = model({"issues": [], "overall": "ok"})
        pipeline.prepare(CANDIDATE, self.db, call=call, workdir=self.wd, cache=self.cache)
        return editor.edit(self.wd, call=call)

    def admit(self, rec):
        return editor.admit_with_record(self.db, self.wd / "edited.json", self.wd / "evidence.json", rec)

    def test_hand_made_record_with_empty_or_legacy_review_is_refused(self):
        rec = self.hand_record(); h = rec["final_content_sha256"]
        empty = copy.deepcopy(rec); empty["rounds"][-1]["review_after"] = {"_content_sha256": h, "_schema": schemas.REVIEW_SCHEMA}
        a = self.admit(empty); self.assertFalse(a["admitted"]); self.assertIn("not a valid review", " ".join(a["problems"]))
        legacy = copy.deepcopy(rec); legacy["rounds"][-1]["review_after"].pop("_schema")
        a = self.admit(legacy); self.assertFalse(a["admitted"]); self.assertIn("legacy record", " ".join(a["problems"]))

    def test_record_cannot_hide_findings_of_its_own_final_review(self):
        rec = self.hand_record()
        hidden = copy.deepcopy(rec); hidden["rounds"][-1]["review_after"]["quote_mismatches"] = ["引语与证据不一致"]
        self.assertEqual(hidden["remaining"], [])                               # the record claims nothing is open...
        a = self.admit(hidden); self.assertFalse(a["admitted"])                  # ...but admission recomputes from the review
        self.assertIn("quote_mismatches", " ".join(a["problems"]))
        a = self.admit(rec); self.assertTrue(a["admitted"], a)


if __name__ == "__main__":
    unittest.main()

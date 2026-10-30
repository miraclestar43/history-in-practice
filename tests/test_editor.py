import json, shutil, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src")); sys.path.insert(0, str(Path(__file__).parent))
from history_in_practice import registry, state, editor, render, checks
from test_registry_pipeline import CANDIDATE, ALIASES, fake_call_factory
from history_in_practice import pipeline
ROOT = Path(__file__).resolve().parents[1]
FIX = {"issues": [{"severity": "fix", "section": "hook", "para": 0, "problem": "陈平降汉写得太满", "suggestion": "改为陈平投汉"}], "overall": "x"}


def scripted(edit_reply, rereview_issues=None):
    """Fake model: original review raises FIX; the editor returns `edit_reply`; later reviews return `rereview_issues`."""
    base = fake_call_factory(); n = {"review": 0}
    def call(prompt, timeout_s=0, **kw):
        r = base(prompt, timeout_s=timeout_s)
        if "事实编辑" in prompt:
            r["text"] = json.dumps(edit_reply, ensure_ascii=False)
        elif "事实审稿人" in prompt:
            n["review"] += 1
            r["text"] = json.dumps(FIX if n["review"] == 1 else {"issues": rereview_issues or [], "overall": "ok"}, ensure_ascii=False)
        return r
    return call


class EditorStage(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); self.cache = Path(self.td.name) / "cache"; self.cache.mkdir()
        shutil.copy(ROOT / "tests/fixtures/A-SJ56.txt", self.cache / "A-SJ56.txt")
        (self.cache / "A-SJ56.meta.json").write_text(json.dumps({"status": "evidence_usable", "source_id": "A-SJ56"}))
        self.db = state.connect(Path(self.td.name) / "s.sqlite"); registry.init(self.db, ALIASES)
        self.wd = Path(self.td.name) / CANDIDATE["candidate_id"]

    def tearDown(self):
        self.td.cleanup()

    def prep(self, call):
        return pipeline.prepare(CANDIDATE, self.db, call=call, workdir=self.wd, cache=self.cache)

    def good_edit(self):
        return {"edits": [{"path": "sections.hook.0.zh", "find": "陈平降汉", "replace": "陈平投汉", "issues": ["R1"], "reason": "收窄"},
                          {"path": "sections.hook.0.en", "find": "陈平降汉", "replace": "Chen Ping joined Han", "issues": ["R1"], "reason": "match zh"}],
                "dispositions": [{"issue": "R1", "action": "fixed", "reason": "改为投汉"}]}

    def test_fix_issue_is_edited_rereviewed_bound_and_admitted(self):
        call = scripted(self.good_edit()); r = self.prep(call)
        self.assertEqual(r["outcome"], "pending_review"); self.assertIn("fix/block", r["reason"])
        rec = editor.edit(self.wd, call=call)
        self.assertEqual(rec["outcome"], "admissible", rec["remaining"]); self.assertEqual(rec["edits_total"], 2)
        r1 = rec["rounds"][0]
        self.assertEqual(r1["issues_in"][0]["id"], "R1"); self.assertEqual(r1["dispositions"][0]["action"], "fixed")
        self.assertEqual(r1["edits_applied"][0]["before"].count("陈平降汉"), 1)
        o = json.loads((self.wd / "edited.json").read_text()); render.finalize(o)
        self.assertEqual(rec["final_content_sha256"], o["content_sha256"]); self.assertEqual(r1["review_after"]["_content_sha256"], o["content_sha256"])
        self.assertIn("陈平投汉", o["sections"][0]["paras"][0]["zh"]); self.assertIn("joined", o["sections"][0]["paras"][0]["en"])
        a = editor.admit_with_record(self.db, self.wd / "edited.json", self.wd / "evidence.json", rec); self.assertTrue(a["admitted"], a)
        self.assertEqual(state.get(self.db, CANDIDATE["candidate_id"])["approval"], "editor-record")

    def test_unapplicable_edit_stays_pending_and_needs_named_exception(self):
        bad = {"edits": [{"path": "sections.hook.0.zh", "find": "不存在的原文", "replace": "x", "issues": ["R1"], "reason": "?"}],
               "dispositions": [{"issue": "R1", "action": "fixed", "reason": "?"}]}
        call = scripted(bad); self.prep(call); rec = editor.edit(self.wd, call=call)
        self.assertEqual(rec["outcome"], "pending_review"); self.assertEqual(rec["rounds"][0]["edits_failed"][0]["error"].split(":")[0], "ValueError")
        self.assertEqual(len(rec["rounds"]), 1)                                   # no progress: the loop stops, it does not spin
        self.assertTrue(rec["remaining"])
        a = editor.admit_with_record(self.db, self.wd / "edited.json", self.wd / "evidence.json", rec)
        self.assertFalse(a["admitted"]); self.assertIn("exception", a["hint"])
        a = editor.admit_with_record(self.db, self.wd / "edited.json", self.wd / "evidence.json", rec, exception="editor-in-chief accepts R1 wording")
        self.assertTrue(a["admitted"]); self.assertTrue(state.get(self.db, CANDIDATE["candidate_id"])["approval"].startswith("exception: "))

    def test_record_does_not_cover_later_changes_or_other_evidence(self):
        call = scripted(self.good_edit()); self.prep(call); rec = editor.edit(self.wd, call=call)
        o = json.loads((self.wd / "edited.json").read_text()); o["sections"][0]["paras"][0]["zh"] += "又改了一句。"
        p = self.wd / "tampered.json"; p.write_text(json.dumps(o, ensure_ascii=False))
        a = editor.admit_with_record(self.db, p, self.wd / "evidence.json", rec, exception="any reason")
        self.assertFalse(a["admitted"]); self.assertIn("article content differs", " ".join(a["problems"]))  # not overridable
        ev = json.loads((self.wd / "evidence.json").read_text()); ev["excerpts"][0]["quote"] += "。"
        q = self.wd / "ev2.json"; q.write_text(json.dumps(ev, ensure_ascii=False))
        a = editor.admit_with_record(self.db, self.wd / "edited.json", q, rec)
        self.assertFalse(a["admitted"]); self.assertIn("evidence differs", " ".join(a["problems"]))

    def test_unedited_pending_draft_cannot_be_admitted_by_status_change(self):
        call = scripted({"edits": [], "dispositions": []}); self.prep(call)
        rec = editor.edit(self.wd, call=call)                                     # model changes nothing
        self.assertEqual(rec["outcome"], "pending_review"); self.assertEqual(rec["edits_total"], 0)
        a = editor.admit_with_record(self.db, self.wd / "article.json", self.wd / "evidence.json", rec)
        self.assertFalse(a["admitted"])
        self.assertEqual(state.get(self.db, CANDIDATE["candidate_id"])["status"], "pending_review")

    def test_rereview_raising_new_issue_runs_second_round_then_stops(self):
        call = scripted(self.good_edit(), rereview_issues=[{"severity": "fix", "section": "story", "para": 0, "problem": "新问题"}])
        self.prep(call); rec = editor.edit(self.wd, call=call)
        self.assertEqual(len([r for r in rec["rounds"] if r["round"]]), 2)      # bounded: at most MAX_ROUNDS
        self.assertEqual(rec["outcome"], "pending_review"); self.assertIn("新问题", json.dumps(rec["remaining"], ensure_ascii=False))


    def test_second_attempt_is_seeded_with_the_open_issues(self):
        call = scripted({"edits": [], "dispositions": []}); self.prep(call); rec = editor.edit(self.wd, call=call)
        self.assertEqual(rec["outcome"], "pending_review")
        w2 = self.wd.parent / "attempt-2"; w2.mkdir()
        shutil.copy(self.wd / "edited.json", w2 / "article.json"); shutil.copy(self.wd / "evidence.json", w2 / "evidence.json")
        (w2 / "seed_issues.json").write_text(json.dumps(rec["remaining"], ensure_ascii=False))
        rec2 = editor.edit(w2, call=scripted(self.good_edit()))
        self.assertEqual(rec2["seeded_issues"], len(rec["remaining"])); self.assertGreaterEqual(len([r for r in rec2["rounds"] if r["round"]]), 1)
        self.assertTrue(rec2["rounds"][0]["issues_in"][0]["id"].startswith("S"))

    def test_evidenced_rejection_counts_as_progress_and_new_issues_get_a_round(self):
        rej = {"edits": [], "dispositions": [{"issue": "R1", "action": "rejected", "reason": "E1 原文「平遂至修武降漢」支持现写法"}]}
        call = scripted(rej, rereview_issues=[{"severity": "fix", "section": "story", "para": 0, "problem": "另一个问题"}])
        self.prep(call); rec = editor.edit(self.wd, call=call)
        self.assertEqual(rec["rounds"][0]["carried_over"], [])                      # rejected with a reason: resolved
        self.assertEqual(len([r for r in rec["rounds"] if r["round"]]), 2)          # the new issue still gets a round

if __name__ == "__main__":
    unittest.main()

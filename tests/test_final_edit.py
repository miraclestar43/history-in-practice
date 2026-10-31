"""Named final editor (final_edit.py): every issue fixed or rejected with a verifiable quote, record bound to the final text,
no exceptions, and nothing admitted when the editor's output is incomplete. The model is a scripted fake; the real CLI
is exercised by validation/claude_runtime_check.py."""
import json, os, shutil, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src")); sys.path.insert(0, str(Path(__file__).parent))
from history_in_practice import registry, state, editor, pipeline, final_edit, render, claude_cli
from test_registry_pipeline import CANDIDATE, ALIASES, fake_call_factory
ROOT = Path(__file__).resolve().parents[1]
CID = CANDIDATE["candidate_id"]


def reply(obj):
    t = json.dumps(obj, ensure_ascii=False)
    return {"rc": 0, "killed": None, "wall_s": 0.1, "prompt_bytes": 1, "prompt_chars": 1, "out_bytes": len(t), "out_chars": len(t),
            "stderr": "", "text": t, "meta": {"model": "claude-opus-5-5", "usage": {"output_tokens": 10}}}


class FinalEditor(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); t = Path(self.td.name)
        os.environ["HIP_DATA_DIR"] = str(t / "data")
        self.cache = t / "cache"; self.cache.mkdir()
        shutil.copy(ROOT / "tests/fixtures/A-SJ56.txt", self.cache / "A-SJ56.txt")
        (self.cache / "A-SJ56.meta.json").write_text(json.dumps({"status": "evidence_usable", "source_id": "A-SJ56"}))
        self.db = state.connect(t / "s.sqlite"); registry.init(self.db, ALIASES)
        self.old = final_edit.OUT_ROOT, final_edit.CANDIDATE_DIR
        final_edit.OUT_ROOT, final_edit.CANDIDATE_DIR = t / "auto", t / "candidates"; final_edit.CANDIDATE_DIR.mkdir()
        # MiMo stage leaves one open issue (the situation the final editor exists for)
        base = fake_call_factory(); n = {"r": 0}
        def mimo(prompt, timeout_s=0, **kw):
            r = base(prompt, timeout_s=timeout_s)
            if "事实审稿人" in prompt:
                n["r"] += 1
                r["text"] = json.dumps({"issues": [{"severity": "fix", "section": "hook", "para": 0, "problem": "陈平降汉写得太满"}], "overall": "x"},
                                       ensure_ascii=False)
            return r
        wd = t / "wd" / CID
        pipeline.prepare(CANDIDATE, self.db, call=mimo, workdir=wd, cache=self.cache)
        rec = editor.edit(wd, call=mimo)
        out = final_edit.OUT_ROOT / CID; out.mkdir(parents=True)
        shutil.copy(wd / "edited.json", out / "article.json"); shutil.copy(wd / "evidence.json", out / "evidence.json")
        (out / "editor_record.json").write_text(json.dumps(rec, ensure_ascii=False))
        state.transition(self.db, CID, "prepared", note="t"); state.transition(self.db, CID, "pending_review", note="t", reason="editor: 1 open")
        self.o = json.loads((out / "article.json").read_text()); render.finalize(self.o)
        self.ev = json.loads((out / "evidence.json").read_text())
        self.paths = [p for p, _, _ in editor.fields(self.o)]
        self.inh = final_edit.inherited_issues(CID, self.o, self.ev)
        e1 = self.ev["excerpts"][0]; self.real_quote = {"id": e1["id"], "quote": e1["quote"][:8]}

    def tearDown(self):
        final_edit.OUT_ROOT, final_edit.CANDIDATE_DIR = self.old
        os.environ.pop("HIP_DATA_DIR"); self.td.cleanup()

    def fields(self, ids=()):
        return [{"path": p, "checked": sorted(final_edit.CHECKS), "issue_ids": list(ids) if p == "sections.hook.0" else []} for p in self.paths]

    def script(self, revise=None, verify_issues=None, audit=None):
        hook = self.o["sections"][0]["paras"][0]
        audit = audit or {"fields": self.fields(["F1"]), "issues": [{"id": "F1", "path": "sections.hook.0", "category": "facts", "severity": "fix",
                          "problem": "“降”字证据不支持", "evidence": [], "proposed": "改为投"}],
                          "inherited": [{"id": i["id"], "verdict": "duplicate", "same_as": "F1", "rationale": "同一问题"} for i in self.inh]}
        revise = revise or {"changes": [{"path": "sections.hook.0.zh", "text": hook["zh"].replace("降", "投"), "issues": ["F1"]},
                                        {"path": "sections.hook.0.en", "text": "Chen Ping joined Han.", "issues": ["F1"]}],
                            "dispositions": [{"issue": "F1", "action": "fixed", "rationale": "降改为投，中英同步"}]}
        seq = {"verify": 0}
        def call(prompt, timeout_s=0, **kw):
            if "【问题清单】" in prompt:
                return reply(revise(prompt) if callable(revise) else revise)
            if "定稿" in prompt:
                seq["verify"] += 1
                iss = verify_issues(seq["verify"]) if callable(verify_issues) else []
                return reply({"fields": self.fields(), "issues": iss, "overall": "ok"})
            return reply(audit)
        return call

    def run_admit(self, call):
        rec = final_edit.run(CID, self.db, call=call)
        out = final_edit.OUT_ROOT / CID / "final"
        a = final_edit.admit(self.db, out / "article.json", out / "evidence.json", rec)
        return rec, a

    def test_happy_path_binds_identity_hashes_and_replays(self):
        rec, a = self.run_admit(self.script())
        self.assertEqual(rec["outcome"], "admissible", rec.get("open_issues")); self.assertTrue(a["admitted"], a)
        self.assertTrue(state.get(self.db, CID)["approval"].startswith("final-editor: Pi Claude"))
        self.assertEqual(rec["editor"]["name"], "Pi Claude"); self.assertTrue(rec["editor"]["cli_version"])
        base = json.loads((final_edit.OUT_ROOT / CID / "final/base_article.json").read_text())
        self.assertEqual(final_edit.replay(base, rec["edits"])["content_sha256"], rec["final_content_sha256"])
        self.assertEqual({i["id"] for i in self.inh} - {i["id"] for i in rec["issues"]}, set())     # every MiMo issue carried and decided
        self.assertIn("elapsed_min", rec); self.assertTrue(rec["calls"])

    def test_rejection_needs_a_quote_that_really_is_in_the_evidence(self):
        fake = {"changes": [], "dispositions": [{"issue": "F1", "action": "rejected", "rationale": "证据支持", "evidence": [{"id": self.real_quote["id"], "quote": "子虚乌有之句"}]}]}
        rec, a = self.run_admit(self.script(revise=fake))
        self.assertEqual(rec["outcome"], "pending_review"); self.assertIn("F1", rec["open_issues"]); self.assertFalse(a["admitted"])
        real = {"changes": [], "dispositions": [{"issue": "F1", "action": "rejected", "rationale": "证据原文支持", "evidence": [self.real_quote]}]}
        self.tearDown(); self.setUp()
        rec, a = self.run_admit(self.script(revise=real))
        self.assertEqual(rec["outcome"], "admissible", rec["open_issues"]); self.assertTrue(a["admitted"], a)

    def test_fixed_without_a_change_stays_open(self):
        rec, a = self.run_admit(self.script(revise={"changes": [], "dispositions": [{"issue": "F1", "action": "fixed", "rationale": "已改"}]}))
        self.assertEqual(rec["outcome"], "pending_review"); self.assertFalse(a["admitted"])

    def test_verify_findings_get_a_bounded_round_then_stay_open(self):
        always = lambda k: [{"id": "1", "path": "sections.story.0", "category": "inner_life", "severity": "fix", "problem": f"无证据的动机{k}", "evidence": []}]
        story = self.o["sections"][2]["paras"][0]; k = {"n": 0}
        def fix_all(prompt):                                  # fixes whatever it is given (F1 in round 1, V1-1 in round 2)
            todo = json.loads(prompt.rsplit("【问题清单】", 1)[1].split("\n\n[", 1)[0]); k["n"] += 1
            return {"changes": [{"path": "sections.story.0.zh", "text": story["zh"] + "。" * k["n"], "issues": [t["id"] for t in todo]},
                                {"path": "sections.story.0.en", "text": story["en"] + "." * k["n"], "issues": [t["id"] for t in todo]}],
                    "dispositions": [{"issue": t["id"], "action": "fixed", "rationale": "删去无据内容"} for t in todo]}
        rec, a = self.run_admit(self.script(revise=fix_all, verify_issues=always))
        self.assertEqual(len(rec["rounds"]), final_edit.MAX_ROUNDS); self.assertEqual(rec["outcome"], "pending_review"); self.assertFalse(a["admitted"])
        self.assertTrue(any(i.startswith(f"V{final_edit.MAX_ROUNDS}-") for i in rec["open_issues"]))

    def test_note_cannot_hide_a_fact_problem_and_incomplete_coverage_fails(self):
        bad = {"fields": self.fields()[:-3], "issues": [{"id": "F1", "path": "sections.hook.0", "category": "facts", "severity": "note", "problem": "p"}],
               "inherited": []}
        self.assertTrue(final_edit.audit_schema(self.paths, [i["id"] for i in self.inh])(bad))
        rec, a = self.run_admit(self.script(audit=bad))
        self.assertTrue(rec["failure"].startswith("audit failed")); self.assertEqual(rec["outcome"], "pending_review"); self.assertFalse(a["admitted"])

    def test_tampering_and_exceptions_are_refused(self):
        rec = final_edit.run(CID, self.db, call=self.script()); out = final_edit.OUT_ROOT / CID / "final"
        o = json.loads((out / "article.json").read_text()); o["sections"][1]["paras"][0]["zh"] += "又加一句。"
        (out / "t.json").write_text(json.dumps(o, ensure_ascii=False))
        a = final_edit.admit(self.db, out / "t.json", out / "evidence.json", rec); self.assertFalse(a["admitted"])
        self.assertIn("content differs", " ".join(a["problems"]))
        forged = json.loads(json.dumps(rec)); forged["edits"][0]["after"] = "别的文字"
        a = final_edit.admit(self.db, out / "article.json", out / "evidence.json", forged); self.assertIn("edit log", " ".join(a["problems"]))
        a = final_edit.admit(self.db, out / "article.json", out / "evidence.json", rec, exception="owner says fine"); self.assertFalse(a["admitted"])
        a = editor.admit_with_record(self.db, out / "article.json", out / "evidence.json", rec); self.assertTrue(a["admitted"], a)   # dispatches

    def test_second_attempt_continues_from_the_previous_final_text_and_its_open_issues(self):
        always = lambda k: [{"id": "1", "path": "sections.story.0", "category": "inner_life", "severity": "fix", "problem": "无证据的动机", "evidence": []}]
        story = self.o["sections"][2]["paras"][0]; n = {"k": 0}
        def fix_all(prompt):                                  # a different text each time (an identical text is not a change)
            todo = json.loads(prompt.rsplit("【问题清单】", 1)[1].split("\n\n[", 1)[0]); n["k"] += 1
            return {"changes": [{"path": "sections.story.0.zh", "text": story["zh"] + "删" * n["k"], "issues": [t["id"] for t in todo]},
                                {"path": "sections.story.0.en", "text": story["en"] + " cut" * n["k"], "issues": [t["id"] for t in todo]}],
                    "dispositions": [{"issue": t["id"], "action": "fixed", "rationale": "删去无据内容"} for t in todo]}
        rec1 = final_edit.run(CID, self.db, call=self.script(revise=fix_all, verify_issues=always))
        self.assertEqual(rec1["outcome"], "pending_review")
        def audit2(prompt):                                   # judges whatever it inherits
            inh = json.loads(prompt.split("【遗留问题】\n", 1)[1].split("\n\n【已知污染】", 1)[0])
            return {"fields": self.fields(), "issues": [], "inherited": [{"id": i["id"], "verdict": "valid", "rationale": "成立"} for i in inh]}
        base = self.script(revise=fix_all)
        def call(prompt, timeout_s=0, **kw):
            if "【遗留问题】" in prompt and "【问题清单】" not in prompt:
                return reply(audit2(prompt))
            return base(prompt, timeout_s)
        rec2 = final_edit.run(CID, self.db, call=call)
        self.assertEqual(rec2["base_content_sha256"], rec1["final_content_sha256"])          # continues from attempt 1's text
        self.assertEqual([i["model_id"] for i in rec2["inherited"]], rec1["open_issues"])    # with attempt 1's open issues
        self.assertEqual(rec2["prior_record_sha256"], editor.sha(rec1))
        out = final_edit.OUT_ROOT / CID / "final"
        self.assertTrue((out / "attempt-1_final_editor_record.json").exists() and (out / "attempt-2_final_editor_record.json").exists())
        self.assertEqual(rec2["outcome"], "admissible", rec2["open_issues"])
        a = final_edit.admit(self.db, out / "article.json", out / "evidence.json", rec2); self.assertTrue(a["admitted"], a)

    def test_real_cli_is_never_called_without_a_subscription_login(self):
        old = claude_cli.CONFIG_DIR; claude_cli.CONFIG_DIR = self.td.name + "/empty-config"
        try:
            rec = final_edit.run(CID, self.db)                                  # default call = claude_cli.call -> preflight
        finally:
            claude_cli.CONFIG_DIR = old
        self.assertEqual(rec["outcome"], "not_run"); self.assertRegex(rec["reason"], "not logged in|not installed")

    def test_subscription_limit_is_a_health_failure_not_an_attempt(self):
        def limited(prompt, timeout_s=0, **kw):
            r = reply({}); r.update(text="", meta={"model": "claude-opus-5-5", "error": "Claude AI usage limit reached|1793430000", "is_error": True})
            return r
        rec = final_edit.run(CID, self.db, call=limited)
        self.assertEqual(rec["outcome"], "pending_review"); self.assertTrue(final_edit.health_failure(rec["failure"]), rec["failure"])
        self.assertEqual(final_edit.attempts_used(CID), 0)                     # the edition keeps both editorial attempts
        self.assertFalse(final_edit.health_failure("schema: issues[0].path missing"))

    def test_nightly_queue_stops_and_reports_health(self):
        from history_in_practice import cli
        old_pre, old_one = claude_cli.preflight, cli._final_one
        try:
            claude_cli.preflight = lambda *a, **k: ["not logged in (config X)"]
            cli._final_one = lambda d, cid: self.fail("final editor called without a passing preflight")
            out, h = cli._final_queue(self.db, 3, 60)
            self.assertEqual((out, h["final_editor"]), ([], "unavailable"))
            hp = Path(os.environ["HIP_DATA_DIR"]) / "health/final_editor.json"; self.assertEqual(json.loads(hp.read_text())["final_editor"], "unavailable")
            claude_cli.preflight = lambda *a, **k: []; calls = []
            cli._final_one = lambda d, cid: calls.append(cid) or {"edition": cid, "outcome": "health", "reason": "Claude AI usage limit reached"}
            out, h = cli._final_queue(self.db, 3, 60)
            self.assertEqual(calls, [CID]); self.assertEqual(h["final_editor"], "degraded")
            self.assertEqual(state.get(self.db, CID)["status"], "pending_review")
        finally:
            claude_cli.preflight, cli._final_one = old_pre, old_one


if __name__ == "__main__":
    unittest.main()

"""Named final editor (final_edit.py): every issue fixed or rejected with a verifiable quote, record bound to the final text,
no exceptions, nothing admitted when the editor's output is incomplete, and admission only after a clean source-context
review (context.py) of the exact final text; a non-clean review is carried into the next attempt (bounded, max_attempts). The model is a scripted fake; the real CLI
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
        self.cache = t / "data" / "source_cache"; self.cache.mkdir(parents=True)     # the default cache path (data_dir()/source_cache)
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
        wd = self.wd = t / "wd" / CID
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
            if "【阅读范围】" in prompt:
                return reply(self.context_reply(prompt))
            if "【问题清单】" in prompt:
                return reply(revise(prompt) if callable(revise) else revise)
            if "定稿" in prompt:
                seq["verify"] += 1
                iss = verify_issues(seq["verify"]) if callable(verify_issues) else []
                return reply({"fields": self.fields(), "issues": iss, "overall": "ok"})
            return reply(audit)
        return call

    @staticmethod
    def context_reply(prompt, verdict="not_a_source_claim", **extra):
        flagged = json.loads(prompt.split("【待核断言】\n", 1)[1]) if "【待核断言】" in prompt else []
        return dict({"episode": [], "additions": [], "context_issues": [], "overall": "ok",
                     "claims": [{"id": f["id"], "verdict": verdict, "scope": "全篇", "source_ids": ["A-SJ56"]} for f in flagged]}, **extra)

    def run_admit(self, call):
        rec = final_edit.run(CID, self.db, call=call)
        out = final_edit.OUT_ROOT / CID / "final"
        final_edit.run_context(CID, call=call)
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
        a = final_edit.admit(self.db, out / "article.json", out / "evidence.json", rec)
        self.assertEqual(a["problems"], ["no source-context review for this content"])        # the final editor alone is not enough
        final_edit.run_context(CID, call=self.script())
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
        final_edit.run_context(CID, call=call)
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
            cli._final_one = lambda d, cid, **kw: self.fail("final editor called without a passing preflight")
            out, h = cli._final_queue(self.db, 3, 60)
            self.assertEqual((out, h["final_editor"]), ([], "unavailable"))
            hp = Path(os.environ["HIP_DATA_DIR"]) / "health/final_editor.json"; self.assertEqual(json.loads(hp.read_text())["final_editor"], "unavailable")
            claude_cli.preflight = lambda *a, **k: []; calls = []
            cli._final_one = lambda d, cid, **kw: calls.append(cid) or {"edition": cid, "outcome": "health", "reason": "Claude AI usage limit reached"}
            out, h = cli._final_queue(self.db, 3, 60)
            self.assertEqual(calls, [CID]); self.assertEqual(h["final_editor"], "degraded")
            self.assertEqual(state.get(self.db, CID)["status"], "pending_review")
        finally:
            claude_cli.preflight, cli._final_one = old_pre, old_one

    def test_carried_checker_issue_closes_only_when_the_checker_is_silent_at_that_location(self):
        rec, a = self.run_admit(self.script()); self.assertTrue(a["admitted"], a)
        out = final_edit.OUT_ROOT / CID / "final"; o = json.loads((out / "article.json").read_text()); ev = json.loads((out / "evidence.json").read_text())
        base = json.loads((out / "base_article.json").read_text())
        carried = {"id": "P9", "origin": "inherited final-editor previous attempt C2-9", "severity": "fix", "disposition": "duplicate",
                   "same_as": "NOPE", "problem": "checker: today[0] repeats the open-question scenario: shared phrases 「x」"}
        r2 = dict(rec, issues=rec["issues"] + [carried])
        self.assertEqual(final_edit.verify_final_record(o, ev, r2, base), [])           # checker silent at today[0]: closed
        o2 = json.loads(json.dumps(o)); today = next(s for s in o2["sections"] if s["id"] == "today")
        rep = "你要先把几个目标的先后次序公开写出来，再把每条理由改写成可以逐条检验的清单"
        today["paras"][0]["zh"] = rep + "。"; o2["reflection"]["scenario"]["zh"] = "小组争论时，" + rep + "。"; render.finalize(o2)
        self.assertTrue(any("today[0]" in x or "P9" in x for x in final_edit.verify_final_record(o2, ev, dict(r2, final_content_sha256=o2["content_sha256"]), base)))

    def _patch_cli(self, call):
        old = (claude_cli.call, claude_cli.preflight, claude_cli.version)
        claude_cli.call, claude_cli.preflight, claude_cli.version = call, (lambda *a, **k: []), (lambda: "test-double")
        self.addCleanup(lambda: setattr(claude_cli, "call", old[0]) or setattr(claude_cli, "preflight", old[1]) or setattr(claude_cli, "version", old[2]))

    def test_unattended_context_finding_is_repaired_in_the_next_attempt_then_admitted(self):
        """A text the final editor passed has a sentence the source contradicts just past an excerpt: the context review
        cuts the decisive line into the pack and blocks admission; the next attempt (same _final_one run, bounded) gets the
        finding with the quote and the expanded evidence, fixes it, and a clean review of the new text admits it."""
        from history_in_practice import cli
        src = (self.cache / "A-SJ56.txt").read_text(encoding="utf-8")
        ev0 = json.loads((final_edit.OUT_ROOT / CID / "evidence.json").read_text())
        last = max(ev0["excerpts"], key=lambda e: e["offset"]); norm = __import__("history_in_practice.evidence", fromlist=["x"]).normalise(src, True)
        after = norm[last["offset"] + len(last["quote"]): last["offset"] + len(last["quote"]) + 40]
        self.assertGreater(len(after), 20)
        story = next(s for s in self.o["sections"] if s["id"] == "story")
        claim_zh = "原文没有记载此后的结果。"; seen = {"ctx": 0, "carried": None}
        base = self.script()
        def call(prompt, timeout_s=0, **kw):
            if "【阅读范围】" in prompt:
                seen["ctx"] += 1
                flagged = json.loads(prompt.split("【待核断言】\n", 1)[1]) if "【待核断言】" in prompt else []
                bad = [f for f in flagged if f["sentence"] == claim_zh]
                if bad:
                    return reply(self.context_reply(prompt, claims=[
                        {"id": f["id"], "verdict": "contradicted" if f in bad else "not_a_source_claim", "source_ids": ["A-SJ56"], "scope": "全篇",
                         "quote": {"source_id": "A-SJ56", "quote": after[:12]}, "fix": "按来源写出结果"} for f in flagged],
                        additions=[{"source_id": "A-SJ56", "start": after[:6], "end": after[14:20], "why": "紧接摘录的结果"}]))
                return reply(self.context_reply(prompt))
            if "【遗留问题】" in prompt and "【问题清单】" not in prompt and "来源上下文核查" in prompt.split("【遗留问题】\n", 1)[-1][:3000]:
                inh = json.loads(prompt.split("【遗留问题】\n", 1)[1].split("\n\n【已知污染】", 1)[0]); seen["carried"] = (inh, prompt)
                return reply({"fields": self.fields(["F1"]), "issues": [{"id": "F1", "path": "sections.hook.0", "category": "facts", "severity": "fix",
                              "problem": "删去与来源矛盾的断言", "evidence": [], "proposed": "删"}],
                              "inherited": [{"id": i["id"], "verdict": "duplicate", "same_as": "F1", "rationale": "同"} for i in inh]})
            if "【问题清单】" in prompt and seen["carried"]:
                cur = json.loads((final_edit.OUT_ROOT / CID / "final" / "article.json").read_text())
                p0 = next(s for s in cur["sections"] if s["id"] == "hook")["paras"][0]
                return reply({"changes": [{"path": "sections.hook.0.zh", "text": p0["zh"].replace(claim_zh, ""), "issues": ["F1"]}],
                              "dispositions": [{"issue": "F1", "action": "fixed", "rationale": "删去"}]})
            if "【问题清单】" in prompt:                                          # attempt 1: plants the claim while fixing F1
                r = json.loads(base(prompt)["text"]); r["changes"][0]["text"] += claim_zh
                return reply(r)
            return base(prompt, timeout_s)
        self._patch_cli(call)
        res = cli._final_one(self.db, CID, deadline=__import__("time").time() + 3600)
        self.assertEqual(res["outcome"], "admitted", res)
        self.assertEqual([r["step"] for r in res["runs"]], ["final edit", "context review", "final edit", "context review"])
        self.assertEqual(res["runs"][1]["outcome"], "needs_work"); self.assertEqual(len(res["runs"][1]["additions"]), 1)
        inh, prompt = seen["carried"]
        self.assertTrue(any("来源上下文核查" in i["problem"] and after[:12] in i["problem"] for i in inh))
        new_id = res["runs"][1]["additions"][0]; self.assertIn(f"[{new_id}]", prompt)                       # the expanded pack is in front of the editor
        out = final_edit.OUT_ROOT / CID / "final"
        self.assertIn(new_id, [e["id"] for e in json.loads((out / "evidence.json").read_text())["excerpts"]])
        self.assertNotIn(claim_zh, (out / "article.zh.md").read_text())
        self.assertEqual(final_edit.current_eligibility(self.db, CID)[0], [])

    def test_attempts_are_bounded_and_counted_since_the_last_demotion(self):
        from history_in_practice import cli
        always = lambda k: [{"id": "1", "path": "sections.story.0", "category": "inner_life", "severity": "fix", "problem": "无证据的动机", "evidence": []}]
        story = self.o["sections"][2]["paras"][0]; n = {"k": 0}
        def fix_all(prompt):
            todo = json.loads(prompt.rsplit("【问题清单】", 1)[1].split("\n\n[", 1)[0]); n["k"] += 1
            return {"changes": [{"path": "sections.story.0.zh", "text": story["zh"] + "删" * n["k"], "issues": [x["id"] for x in todo]}],
                    "dispositions": [{"issue": x["id"], "action": "fixed", "rationale": "删"} for x in todo]}
        base = self.script(revise=fix_all, verify_issues=always)
        def call(prompt, timeout_s=0, **kw):
            if "【遗留问题】" in prompt and "【问题清单】" not in prompt and "来源上下文核查" not in prompt:
                inh = json.loads(prompt.split("【遗留问题】\n", 1)[1].split("\n\n【已知污染】", 1)[0])
                return reply({"fields": self.fields(), "issues": [], "inherited": [{"id": i["id"], "verdict": "valid", "rationale": "成立"} for i in inh]})
            return base(prompt, timeout_s)
        self._patch_cli(call)
        import time as _t
        res = cli._final_one(self.db, CID, deadline=_t.time() + final_edit.MIN_ATTEMPT_MIN * 60 - 1)        # not enough time: nothing starts
        self.assertEqual(res["runs"], []); self.assertIn("deadline", res["stopped"])
        res = cli._final_one(self.db, CID, deadline=_t.time() + 3600)
        self.assertEqual([r["step"] for r in res["runs"]], ["final edit"] * final_edit.MAX_ATTEMPTS)   # all attempts in one run
        self.assertEqual(res["outcome"], "pending_review"); self.assertEqual(state.get(self.db, CID)["status"], "pending_review")
        self.assertEqual(cli._final_one(self.db, CID)["outcome"], "skipped")                            # exhausted; fact threshold unchanged
        res = cli._final_one(self.db, CID, "owner: one more")                                          # one owner-directed attempt
        self.assertEqual(len(res["runs"]), 1); self.assertEqual(cli._final_one(self.db, CID, "owner")["outcome"], "skipped")
        from unittest import mock
        with mock.patch.object(final_edit, "evidence_added_since_last_attempt", lambda cid: ["X-E99"]):
            res = cli._final_one(self.db, CID, "owner: new evidence")                                  # new input: exactly one more
            self.assertEqual(len(res["runs"]), 1); self.assertEqual(res["evidence_added"], ["X-E99"])
            res = cli._final_one(self.db, CID, "owner: again")                                         # hard cap max + 2
            self.assertEqual(res["outcome"], "skipped"); self.assertIn("+ 2 owner-directed", res["reason"])
        self.assertEqual(final_edit.attempts_used(CID, self.db), final_edit.MAX_ATTEMPTS + 2)
        self.db.execute("INSERT INTO transition(edition_id,from_status,to_status,at,note) VALUES(?,?,?,?,?)", (CID, "checked", "pending_review", _t.time() + 1, "t"))
        self.assertEqual(final_edit.attempts_used(CID, self.db), 0); self.assertEqual(final_edit.attempts_used(CID), final_edit.MAX_ATTEMPTS + 2)

    def test_operator_request_goes_to_the_next_attempt_not_straight_to_readmission(self):
        rec, a = self.run_admit(self.script()); self.assertTrue(a["admitted"], a)
        self.assertFalse(final_edit.awaiting_context(CID))                       # reviewed and admitted
        (final_edit.OUT_ROOT / CID / "final" / "context_review.json").unlink()
        self.assertTrue(final_edit.awaiting_context(CID))
        final_edit.write_operator_issues(CID, ["中文比英文单薄：按证据补足背景与经过"], "short zh")
        self.assertFalse(final_edit.awaiting_context(CID))                       # the request needs an attempt first
        seen = {}
        base = self.script()
        def call(prompt, timeout_s=0, **kw):
            if "【遗留问题】\n" in prompt and "【问题清单】" not in prompt and "【阅读范围】" not in prompt:
                seen["inh"] = json.loads(prompt.split("【遗留问题】\n", 1)[1].split("\n\n【已知污染】", 1)[0])
            return base(prompt, timeout_s)
        final_edit.run(CID, self.db, call=call)
        self.assertIn("O1", [i["id"] for i in seen["inh"]]); self.assertIn("单薄", seen["inh"][-1]["problem"])

    def test_verified_inventory_counts_only_editions_admitted_now(self):
        rec, a = self.run_admit(self.script()); self.assertTrue(a["admitted"], a)
        cat = state.get(self.db, CID)["category"]
        inv = pipeline.inventory(self.db, verify=True)
        self.assertEqual(inv["schedulable_by_category"][cat], 1); self.assertEqual(inv["not_currently_eligible"], {})
        (final_edit.OUT_ROOT / CID / "final" / "context_review.json").unlink()                # e.g. never context-reviewed
        inv = pipeline.inventory(self.db, verify=True)
        self.assertEqual(inv["schedulable_by_category"][cat], 0)
        self.assertIn("no source-context review for this content", inv["not_currently_eligible"][CID])
        self.assertEqual(pipeline.inventory(self.db)["schedulable_by_category"][cat], 1)     # the unverified count would inflate

    def test_send_gate_for_admitted_and_archived_copies(self):
        rec, a = self.run_admit(self.script()); self.assertTrue(a["admitted"], a)
        out = final_edit.OUT_ROOT / CID / "final"; o = json.loads((out / "article.json").read_text()); render.finalize(o)
        self.assertEqual(final_edit.send_problems(self.db, o), [])
        test = dict(o, status="test"); self.assertIn("test-edition", final_edit.send_problems(self.db, test)[0])
        cur = state.get(self.db, CID)
        arch = dict(o, status="published", edition_date="2026-11-02",
                    admitted_from={"path": str((out / "article.json").resolve()), "content_sha256": o["content_sha256"], "revision": 1, "approval": cur["approval"]})
        self.assertEqual(final_edit.send_problems(self.db, arch), [])
        bad = json.loads(json.dumps(arch)); bad["sections"][0]["paras"][0]["zh"] += "改。"
        self.assertIn("sections differs from the admitted article", final_edit.send_problems(self.db, bad))
        (out / "context_review.json").unlink()                                   # stale/missing context review
        self.assertIn("no source-context review for this content", final_edit.send_problems(self.db, arch))
        self.assertIn("no source-context review for this content", final_edit.send_problems(self.db, o))

    def test_local_fix_is_scoped_recorded_reverified_and_not_an_attempt(self):
        out = final_edit.OUT_ROOT / CID / "final"
        ev0 = json.loads(json.dumps(self.ev)); e = ev0["excerpts"][0]
        issue = {"id": "1", "path": "sections.story.0", "category": "attribution", "severity": "fix", "problem": "把朋友的理由写成了他的判断",
                 "evidence": [{"id": e["id"], "quote": e["quote"][:8]}], "proposed": "改归属"}
        story0 = self.o["sections"][2]["paras"][0]; n = {"k": 0}
        def fix_all(prompt):
            todo = json.loads(prompt.rsplit("【问题清单】", 1)[1].split("\n\n[", 1)[0]); n["k"] += 1
            return {"changes": [{"path": "sections.story.0.zh", "text": story0["zh"] + "删" * n["k"], "issues": [x["id"] for x in todo]}],
                    "dispositions": [{"issue": x["id"], "action": "fixed", "rationale": "删"} for x in todo]}
        rec = final_edit.run(CID, self.db, call=self.script(revise=fix_all, verify_issues=lambda k: [issue]))
        self.assertEqual(rec["outcome"], "pending_review"); open_id = rec["open_issues"][-1]; n0 = final_edit.attempts_used(CID)
        story = json.loads((out / "article.json").read_text())["sections"][2]["paras"][0]
        clean = self.script(verify_issues=lambda k: [])
        r = final_edit.local_fix(CID, self.db, [{"path": "sections.hook.0.zh", "text": "改"}], [open_id], "t", call=clean)
        self.assertEqual(r["outcome"], "refused"); self.assertIn("outside the fields", r["reason"])          # only the named field          # only the named field
        r = final_edit.local_fix(CID, self.db, [{"path": "sections.story.0.zh", "text": story["zh"] + "（归属已改）"},
                                                {"path": "sections.story.0.en", "text": story["en"] + " (attribution fixed)"}], [open_id], "t", call=clean)
        self.assertEqual(r["outcome"], "admissible", r.get("open_issues")); self.assertEqual(final_edit.attempts_used(CID), n0)
        self.assertEqual(r["local_fixes"][0]["issues"], [open_id]); self.assertEqual(len(r["local_fixes"][0]["edits"]), 2)
        o = json.loads((out / "article.json").read_text())
        self.assertEqual(final_edit.verify_final_record(o, json.loads((out / "evidence.json").read_text()), r,
                                                        json.loads((out / "base_article.json").read_text())), [])   # replays base -> final
        self.assertTrue(final_edit.awaiting_context(CID))                         # context review still due on the new text
        final_edit.run_context(CID, call=clean)
        a = final_edit.admit(self.db, out / "article.json", out / "evidence.json", r); self.assertTrue(a["admitted"], a)
        self.assertEqual(final_edit.local_fix(CID, self.db, [], [open_id], "again", call=clean)["outcome"], "refused")

    def test_local_fix_command_never_starts_a_whole_article_attempt(self):
        # 2026-10-31: the CLI handed off to the queue loop after a local fix, and a revision's demotion had reset the
        # allowance, so unrequested attempts started. Now: context review + admission only.
        from history_in_practice import cli
        from unittest import mock
        import argparse, io, contextlib
        e = self.ev["excerpts"][0]
        issue = {"id": "1", "path": "sections.story.0", "category": "attribution", "severity": "fix", "problem": "归属",
                 "evidence": [{"id": e["id"], "quote": e["quote"][:8]}], "proposed": "改"}
        story0 = self.o["sections"][2]["paras"][0]; n = {"k": 0}
        def fix_all(prompt):
            todo = json.loads(prompt.rsplit("【问题清单】", 1)[1].split("\n\n[", 1)[0]); n["k"] += 1
            return {"changes": [{"path": "sections.story.0.zh", "text": story0["zh"] + "删" * n["k"], "issues": [x["id"] for x in todo]}],
                    "dispositions": [{"issue": x["id"], "action": "fixed", "rationale": "删"} for x in todo]}
        rec = final_edit.run(CID, self.db, call=self.script(revise=fix_all, verify_issues=lambda k: [issue])); open_id = rec["open_issues"][-1]
        out = final_edit.OUT_ROOT / CID / "final"; story = json.loads((out / "article.json").read_text())["sections"][2]["paras"][0]
        hook = json.loads((out / "article.json").read_text())["sections"][0]["paras"][0]
        ch = Path(tempfile.mkdtemp()) / "ch.json"
        ch.write_text(json.dumps([{"path": "sections.story.0.zh", "text": story["zh"] + "（改）"},
                                  {"path": "sections.hook.0.zh", "text": hook["zh"] + "（删去成语释义）"}], ensure_ascii=False))
        self._patch_cli(self.script(verify_issues=lambda k: []))
        a = argparse.Namespace(edition=CID, issue=[open_id], changes=str(ch), reason="t", operator_issue=["sections.hook.0|owner: drop the idiom gloss"])
        n_before = final_edit.attempts_used(CID)
        with mock.patch.object(final_edit, "run", side_effect=AssertionError("no whole-article attempt")), \
             mock.patch.object(final_edit, "run_context", return_value={"outcome": "needs_work", "blocking": ["x"]}), \
             mock.patch.object(cli, "db", return_value=self.db), contextlib.redirect_stdout(io.StringIO()):
            rc = cli.cmd_local_fix(a)
        self.assertEqual(rc, 2); self.assertEqual(final_edit.attempts_used(CID), n_before)
        r = final_edit.prior_final(CID); self.assertEqual(r["outcome"], "admissible")
        ops = [i for i in r["issues"] if i["id"].startswith("OP")]
        self.assertEqual([(i["path"], i["disposition"]) for i in ops], [("sections.hook.0", "fixed")])

    def test_local_fix_of_context_findings_adopts_the_cut_excerpt_and_never_starts_an_attempt(self):
        # 2026-10-31 (胡适 rev2): the context review of an admissible text found a wrong chapter citation and cut a new
        # excerpt. The owner-authorized local fix uses those findings as its basis (CTX-X<n>), may correct the source
        # citation, adopts the expanded pack, then gets one context review: no whole-article path, no attempt counted,
        # earlier records kept byte for byte.
        from history_in_practice import cli, evidence as evmod
        from unittest import mock
        import argparse, io, contextlib
        src = (self.cache / "A-SJ56.txt").read_text(encoding="utf-8"); norm = evmod.normalise(src, True)
        last = max(self.ev["excerpts"], key=lambda e: e["offset"]); after = norm[last["offset"] + len(last["quote"]):][:40]
        rec = final_edit.run(CID, self.db, call=self.script()); self.assertEqual(rec["outcome"], "admissible")
        def needs_work(prompt, timeout_s=0, **kw):
            return reply(self.context_reply(prompt, context_issues=[{"path": "uncertainty_note", "problem": "章节写错",
                                                                     "quote": {"source_id": "A-SJ56", "quote": after[:12]}, "severity": "fix"}],
                                            additions=[{"source_id": "A-SJ56", "start": after[:6], "end": after[14:20], "why": "当事人自述"}]))
        cx = final_edit.run_context(CID, call=needs_work); self.assertEqual(cx["outcome"], "needs_work", cx)
        out = final_edit.OUT_ROOT / CID / "final"
        kept = {f.name: f.read_bytes() for f in out.glob("*.json") if f.name.startswith(("attempt-", "context-"))}
        o = json.loads((out / "article.json").read_text()); note = o["uncertainty_note"]
        ch = Path(tempfile.mkdtemp()) / "ch.json"
        ch.write_text(json.dumps([{"path": "uncertainty_note.zh", "text": note["zh"] + "（章节已更正）"},
                                  {"path": "uncertainty_note.en", "text": note["en"] + " (chapter corrected)"},
                                  {"path": "sources.0.citation", "text": o["sources"][0]["citation"] + "（第七章）"}], ensure_ascii=False))
        # outside the fields the findings name: refused, nothing written
        bad = Path(tempfile.mkdtemp()) / "bad.json"; bad.write_text(json.dumps([{"path": "sections.story.0.zh", "text": "改"}]))
        self.assertEqual(final_edit.local_fix(CID, self.db, json.loads(bad.read_text()), ["CTX-X1"], "t", call=self.script())["outcome"], "refused")
        self._patch_cli(self.script())
        a = argparse.Namespace(edition=CID, issue=["CTX-X1"], changes=str(ch), reason="owner: fix chapter citation",
                               operator_issue=["sources.0.citation|owner: cite the right chapter"])
        n_before = final_edit.attempts_used(CID)
        with mock.patch.object(final_edit, "run", side_effect=AssertionError("no whole-article attempt")), \
             mock.patch.object(cli, "_final_one", side_effect=AssertionError("no queue hand-off")), \
             mock.patch.object(cli, "db", return_value=self.db), contextlib.redirect_stdout(io.StringIO()):
            rc = cli.cmd_local_fix(a)
        self.assertEqual(rc, 0); self.assertEqual(final_edit.attempts_used(CID), n_before)
        self.assertEqual(state.get(self.db, CID)["status"], "checked"); self.assertEqual(final_edit.current_eligibility(self.db, CID)[0], [])
        r = final_edit.prior_final(CID); new_ev = json.loads((out / "evidence.json").read_text())
        self.assertEqual(r["evidence_expanded"][0]["added"], [x["id"] for x in cx["additions"]])
        self.assertIn(cx["additions"][0]["id"], [e["id"] for e in new_ev["excerpts"]])
        self.assertTrue(all(e in new_ev["excerpts"] for e in self.ev["excerpts"]))                     # old excerpts unchanged
        self.assertIn("（第七章）", json.loads((out / "article.json").read_text())["sources"][0]["citation"])
        self.assertEqual([f for f in kept if (out / f).read_bytes() != kept[f]], [])                         # history untouched
        self.assertFalse(any((final_edit.data_dir() / "final_edit" / CID).glob(f"attempt-{n_before + 1}")))

    def test_local_fix_can_correct_pack_metadata_and_reject_an_issue_with_a_verbatim_cut(self):
        # 2026-10-31 (胡适): the pack's source title named the wrong chapter, so the verify pass "contradicted" the right
        # citation. The pack may be corrected (title; verbatim cuts from the cached text, old excerpts unchanged) and the
        # issue rejected with a quote from the corrected pack; a non-unique anchor or a quote not in the pack is refused.
        from history_in_practice import evidence as evmod
        src = (self.cache / "A-SJ56.txt").read_text(encoding="utf-8"); norm = evmod.normalise(src, True)
        last = max(self.ev["excerpts"], key=lambda e: e["offset"]); after = norm[last["offset"] + len(last["quote"]):][:40]
        bad = {"id": "1", "path": "uncertainty_note", "category": "facts", "severity": "fix", "problem": "来源标题与正文不符",
               "evidence": [{"id": self.real_quote["id"], "quote": self.real_quote["quote"]}], "proposed": "改"}
        story0 = self.o["sections"][2]["paras"][0]; n = {"k": 0}
        def fix_all(prompt):
            todo = json.loads(prompt.rsplit("【问题清单】", 1)[1].split("\n\n[", 1)[0]); n["k"] += 1
            return {"changes": [{"path": "sections.story.0.zh", "text": story0["zh"] + "删" * n["k"], "issues": [x["id"] for x in todo]}],
                    "dispositions": [{"issue": x["id"], "action": "fixed", "rationale": "删"} for x in todo]}
        for k in self.ev["sources"]:                              # as a real fetch records it: the hash of the cached text
            self.ev["sources"][k]["text_sha256"] = __import__("hashlib").sha256((self.cache / f"{k}.txt").read_bytes()).hexdigest()
        (final_edit.OUT_ROOT / CID / "evidence.json").write_text(json.dumps(self.ev, ensure_ascii=False))
        rec = final_edit.run(CID, self.db, call=self.script(revise=fix_all, verify_issues=lambda k: [bad])); vid = rec["open_issues"][-1]
        self.assertEqual((rec["outcome"], rec.get("failure")), ("pending_review", None), rec.get("open_issues"))
        sid = self.ev["excerpts"][0]["source_id"]
        fix = {"titles": {sid: "更正后的来源标题"}, "add": [{"source_id": sid, "start": after[:8], "end": after[16:22], "why": "章名"}]}
        rej = [{"issue": vid, "rationale": "来源原文的章名", "evidence": [{"id": "A-SJ56-E99", "quote": after[:8]}]}]
        self.assertIn("quotes verified", final_edit.local_fix(CID, self.db, [], [], "t", call=self.script(), pack_fix=fix, rejections=rej)["reason"])
        r0 = final_edit.local_fix(CID, self.db, [], [], "t", call=self.script(), pack_fix={"add": [{"source_id": sid, "start": "。", "end": "。"}]},
                                  rejections=rej)
        self.assertIn("exactly once", r0["reason"])
        new_id = final_edit.correct_pack(self.ev, fix, self.cache)[1][0]; rej[0]["evidence"][0]["id"] = new_id
        r = final_edit.local_fix(CID, self.db, [], [], "pack title", call=self.script(), pack_fix=fix, rejections=rej)
        self.assertEqual(r["outcome"], "admissible", r.get("open_issues"))
        out = final_edit.OUT_ROOT / CID / "final"; ev2 = json.loads((out / "evidence.json").read_text())
        self.assertEqual(ev2["sources"][sid]["title"], "更正后的来源标题"); self.assertTrue(all(e in ev2["excerpts"] for e in self.ev["excerpts"]))
        self.assertEqual(r["evidence_corrected"][0]["added"], [new_id])
        fix2 = {"locators": {self.ev["excerpts"][0]["id"]: "第一章"}}; ev3 = final_edit.correct_pack(ev2, fix2, self.cache)[0]
        self.assertEqual([{k: v for k, v in e.items() if k != "locator"} for e in ev3["excerpts"]],
                         [{k: v for k, v in e.items() if k != "locator"} for e in ev2["excerpts"]])     # only the label changes
        self.assertEqual(next(i for i in r["issues"] if i["id"] == vid)["disposition"], "rejected")
        o = json.loads((out / "article.json").read_text())
        self.assertEqual(final_edit.verify_final_record(o, ev2, r, json.loads((out / "base_article.json").read_text())), [])

    def test_owner_authorized_revision_archives_rev1_and_readmits_rev2_after_one_attempt(self):
        from history_in_practice import cli
        rec, a = self.run_admit(self.script()); self.assertTrue(a["admitted"], a)
        out = final_edit.OUT_ROOT / CID / "final"; old = json.loads((out / "article.json").read_text()); render.finalize(old)
        new = json.loads(json.dumps(old)); new["sections"][2]["paras"][0]["zh"] += "（删节）"
        self.assertFalse(final_edit.revise_base(CID, self.db, new, "t")["revised"])                 # must be the next revision
        new["revision"] = old["revision"] + 1
        r = final_edit.revise_base(CID, self.db, new, "abridgment"); self.assertTrue(r["revised"], r)
        arch = final_edit.OUT_ROOT / CID / "revisions" / f"rev{old['revision']}"
        self.assertEqual(json.loads((arch / "article.json").read_text())["content_sha256"], old["content_sha256"])   # rev1 kept intact
        self.assertTrue((arch / "final_editor_record.json").exists()); self.assertTrue((arch / "context_review.json").exists())
        cli._demote(self.db, CID, state.get(self.db, CID), "requeued: owner-authorized revision")
        rec2 = final_edit.run(CID, self.db, call=self.script(audit={"fields": self.fields(), "issues": [], "inherited": []}))
        self.assertEqual(rec2["outcome"], "admissible", rec2.get("open_issues"))
        self.assertTrue(final_edit.awaiting_context(CID)); final_edit.run_context(CID, call=self.script())
        a2 = final_edit.admit(self.db, out / "article.json", out / "evidence.json", rec2); self.assertTrue(a2["admitted"], a2)
        self.assertEqual(state.get(self.db, CID)["revision"], old["revision"] + 1)
        self.assertEqual(final_edit.current_eligibility(self.db, CID)[0], [])

    def test_editor_prompts_forbid_inventing_what_the_full_source_lacks(self):
        # 2026-10-31: most context-review blockers were "原文未载/书中未写年份/no account survives" written by the final
        # editor, who sees only the evidence pack. Audit and verify must flag them; revise must not add them.
        for name in ("final_audit.md", "final_verify.md"):
            t = (pipeline.PROMPTS / name).read_text()
            self.assertIn("来源未载类断言", t); self.assertIn("你看到的是证据包，不是完整来源", t)
        self.assertIn("证据包没有不等于来源没有", (pipeline.PROMPTS / "final_revise.md").read_text())

    def test_adopt_admits_records_from_another_data_directory_with_the_same_checks(self):
        """2026-11-01: an article finished in the validation worktree is admitted in production only through admit()."""
        rec, a = self.run_admit(self.script()); self.assertTrue(a["admitted"], a)
        fresh = state.connect(Path(self.td.name) / "other.sqlite"); registry.init(fresh, ALIASES)
        r = final_edit.adopt(fresh, CID); self.assertTrue(r["adopted"], r)
        self.assertEqual(state.get(fresh, CID)["status"], "checked"); self.assertEqual(final_edit.current_eligibility(fresh, CID)[0], [])
        self.assertIn("already known", final_edit.adopt(fresh, CID)["reason"])
        fresh2 = state.connect(Path(self.td.name) / "other2.sqlite"); registry.init(fresh2, ALIASES)
        out = final_edit.OUT_ROOT / CID / "final"; art = json.loads((out / "article.json").read_text())
        art["sections"][2]["paras"][0]["zh"] += "（改动）"; (out / "article.json").write_text(json.dumps(art, ensure_ascii=False))
        r2 = final_edit.adopt(fresh2, CID)                                     # content no longer matches the record
        self.assertFalse(r2["adopted"]); self.assertEqual(state.get(fresh2, CID)["status"], "pending_review")

    def test_local_fix_basis_must_be_verbatim_in_the_pack(self):
        """2026-11-01: a verifier quote with a typo blocks a clear-basis fix; the operator may supply the verbatim basis,
        which is checked against the pack like any other quote."""
        out = final_edit.OUT_ROOT / CID / "final"; e = self.ev["excerpts"][0]
        issue = {"id": "1", "path": "sections.story.0", "category": "attribution", "severity": "fix", "problem": "归属",
                 "evidence": [{"id": e["id"], "quote": "并不存在的引文"}], "proposed": "改归属"}
        story0 = self.o["sections"][2]["paras"][0]
        def fix_all(prompt):
            todo = json.loads(prompt.rsplit("【问题清单】", 1)[1].split("\n\n[", 1)[0])
            return {"changes": [{"path": "sections.story.0.zh", "text": story0["zh"] + "改", "issues": [x["id"] for x in todo]}],
                    "dispositions": [{"issue": x["id"], "action": "fixed", "rationale": "改"} for x in todo]}
        rec = final_edit.run(CID, self.db, call=self.script(revise=fix_all, verify_issues=lambda k: [issue])); vids = rec["open_issues"]
        story = json.loads((out / "article.json").read_text())["sections"][2]["paras"][0]
        ch = [{"path": "sections.story.0.zh", "text": story["zh"] + "（归属）"}, {"path": "sections.story.0.en", "text": story["en"] + " (attribution)"}]
        clean = self.script(verify_issues=lambda k: [])
        self.assertEqual(final_edit.local_fix(CID, self.db, ch, vids, "t", call=clean)["outcome"], "refused")
        bad = final_edit.local_fix(CID, self.db, ch, vids, "t", call=clean, basis={v: [{"id": e["id"], "quote": "也不存在"}] for v in vids})
        self.assertIn("not verbatim", bad["reason"])
        ok = final_edit.local_fix(CID, self.db, ch, vids, "t", call=clean, basis={v: [self.real_quote] for v in vids})
        self.assertEqual(ok["outcome"], "admissible", ok.get("reason"))

    # Owner request 2026-10-31 (reader feedback on 吴起, applied to the writing agent): the reader-first rules must reach
    # every stage that actually writes or judges text -- MiMo draft and English, the MiMo edit rounds, the Claude final
    # audit / revise / verify (also on the owner-authorized revision and local-fix paths) -- and every call records which
    # prompt files it was sent, so a run can show what was loaded rather than what the docs say.
    RULE_ZH = "【讲清楚：读者优先的写法】"
    RULE_EN = "[Make it clear: reader-first rules"

    def _calls(self, path):
        return [json.loads(x) for x in Path(path).read_text().splitlines()]

    def test_every_writing_and_review_stage_loads_the_reader_first_rules_and_records_it(self):
        files = lambda m: {f["file"] for f in m["prompts"]}
        mimo = {m["step"]: files(m) for m in self._calls(self.wd / "calls.jsonl")}       # prepare + editor.edit (setUp)
        self.assertLessEqual({"style_zh.md", "draft_zh_long.md", "reader_first_zh.md"}, mimo["draft_zh"])
        self.assertLessEqual({"translate_en_long.md", "reader_first_en.md"}, mimo["en"])
        self.assertLessEqual({"edit_zh_en.md", "reader_first_zh.md"}, mimo["edit_r1"])
        self.assertIn("parity_en.md", mimo["parity_r1"]); self.assertIn("review_zh.md", mimo["review_zh"])
        sent = {}
        def rec(inner):
            def call(prompt, timeout_s=0, **kw):
                key = ("context" if "【阅读范围】" in prompt else "revise" if "【问题清单】" in prompt else "verify" if "定稿" in prompt else "audit")
                sent.setdefault(key, []).append(prompt); return inner(prompt, timeout_s=timeout_s, **kw)
            return call
        issue = {"id": "1", "path": "sections.story.0", "category": "readability", "severity": "fix", "problem": "两位公主分不清",
                 "evidence": [self.real_quote], "proposed": "写明是谁的妻子"}
        story0 = self.o["sections"][2]["paras"][0]
        def fix_all(prompt):
            todo = json.loads(prompt.rsplit("【问题清单】", 1)[1].split("\n\n[", 1)[0])
            return {"changes": [{"path": "sections.story.0.zh", "text": story0["zh"] + "改", "issues": [x["id"] for x in todo]}],
                    "dispositions": [{"issue": x["id"], "action": "fixed", "rationale": "改"} for x in todo]}
        r = final_edit.run(CID, self.db, call=rec(self.script(revise=fix_all, verify_issues=lambda k: [issue])))
        for k in ("audit", "revise", "verify"):
            self.assertIn(self.RULE_ZH, sent[k][0], k); self.assertNotIn("{{include", sent[k][0])
        self.assertIn("reader_first_zh.md", {f["file"] for c in r["calls"] if c["step"] == "audit" for f in c["prompts"]})
        out = final_edit.OUT_ROOT / CID / "final"; story = json.loads((out / "article.json").read_text())["sections"][2]["paras"][0]
        n = len(sent["verify"])
        final_edit.local_fix(CID, self.db, [{"path": "sections.story.0.zh", "text": story["zh"] + "（公叔的妻子）"},
                                            {"path": "sections.story.0.en", "text": story["en"] + " (Gongshu's wife)"}],
                             [r["open_issues"][-1]], "t", call=rec(self.script()))
        self.assertIn(self.RULE_ZH, sent["verify"][n])                                       # local-fix re-verification
        final_edit.run_context(CID, call=rec(self.script()))
        self.assertTrue(sent["context"][0].startswith(pipeline.load_prompt("context_review")[:40]))
        cx = json.loads((out / "context_review.json").read_text())
        self.assertIn("context_review.md", {f["file"] for c in cx["calls"] for f in c["prompts"] or []})   # templated prompt

    def test_owner_revision_path_audits_with_the_same_rules(self):
        from history_in_practice import cli
        rec, a = self.run_admit(self.script()); self.assertTrue(a["admitted"], a)
        out = final_edit.OUT_ROOT / CID / "final"; new = json.loads((out / "article.json").read_text()); render.finalize(new)
        new["revision"] += 1; new["dek"]["zh"] = "一门婚事，为什么让一位功臣待不下去？"
        self.assertTrue(final_edit.revise_base(CID, self.db, new, "reader-first")["revised"])
        cli._demote(self.db, CID, state.get(self.db, CID), "requeued: owner-authorized revision")
        seen = []
        def call(prompt, timeout_s=0, **kw):
            seen.append(prompt); return self.script(audit={"fields": self.fields(), "issues": [], "inherited": []})(prompt, timeout_s=timeout_s)
        final_edit.run(CID, self.db, call=call)
        self.assertTrue(seen and all(self.RULE_ZH in p for p in seen))

    def test_old_conflicting_rules_are_gone_and_the_application_rule_is_one_scene(self):
        every = {p.stem: pipeline.load_prompt(p.stem) for p in pipeline.PROMPTS.glob("*.md")}
        for name, t in every.items():
            for old in ("恰好两段", "两个场景都不能", "today 仍", "两个具体启发"):
                self.assertNotIn(old, t, name)
        draft = every["style_zh"] + every["draft_zh_long"]
        self.assertIn("today 一节默认不写", draft); self.assertIn("全文只设一个简短的现代应用场景", draft)
        self.assertIn("不要先把全部经过和结局概述一遍", draft)                     # dek/hook division of labour
        self.assertIn("同一称谓指不同的人", draft)
        self.assertIn("Same title, different people", every["translate_en_long"])
        for name in ("final_audit", "final_verify"):        # sj077-2 validation: an unglossed key line was only a note
            self.assertIn("引用的关键文言没有在同段讲清意思（第 7 条）", every[name], name)
        for name in ("final_revise", "edit_zh_en"):                                 # fixing must not move backwards
            self.assertIn("不要恢复初稿或上一轮已经删去的内容", every[name], name)

    def test_checker_signals_two_paragraph_today_and_a_dek_that_retells_the_opening(self):
        from history_in_practice import checks
        o = json.loads(json.dumps(self.o))
        today = next(s for s in o["sections"] if s["id"] == "today")
        if len(today["paras"]) == 1:
            today["paras"].append(dict(today["paras"][0]))
        o["sections"][0]["paras"][0]["zh"] = o["dek"]["zh"] = "公叔先劝国君把公主许配给吴起，再请吴起到家里。"
        f = checks.check(o, self.ev)[0]
        self.assertIn(("CHECK", "readability: today has two paragraphs; the rule is one short application (the scene lives in the question)"), f)
        self.assertTrue(any(lvl == "CHECK" and "dek and hook[0]" in m for lvl, m in f), f)
        self.assertFalse(any(lvl in ("FIX", "BLOCK") and ("today" in m and "two" in m or "dek" in m) for lvl, m in f))


if __name__ == "__main__":
    unittest.main()

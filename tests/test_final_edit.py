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
        self.db.execute("INSERT INTO transition(edition_id,from_status,to_status,at,note) VALUES(?,?,?,?,?)", (CID, "checked", "pending_review", _t.time() + 1, "t"))
        self.assertEqual(final_edit.attempts_used(CID, self.db), 0); self.assertEqual(final_edit.attempts_used(CID), final_edit.MAX_ATTEMPTS)

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


if __name__ == "__main__":
    unittest.main()

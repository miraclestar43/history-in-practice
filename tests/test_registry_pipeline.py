import json, shutil, sqlite3, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import registry, state, pipeline, evidence, editor

ROOT = Path(__file__).resolve().parents[1]
ALIASES = json.loads((ROOT / "config/aliases.json").read_text())


def mk():
    db = sqlite3.connect(":memory:", isolation_level=None); registry.init(db, ALIASES, {"Q-OLD": "Q-NEW"}); return db


BASE = dict(persons=["陈平", "范增", "项羽", "汉王"], year_from=-204, year_to=-204, place="荥阳", action="反间离间项羽与范增",
            spans=[["zh:史記/卷056", 1000, 1200], ["zh:史記/卷007", 7700, 7900]], title="陈平反间")


class Dedup(unittest.TestCase):
    def setUp(self):
        self.db = mk(); registry.reserve(self.db, BASE, status="published")
        registry.reserve(self.db, dict(persons=["Washington"], year_from=1783, year_to=1783, place="newburgh", action="address",
                                       event_qid="Q-NEW", spans=[["en:JCC/24", 1, 50]]), status="published")
        registry.reserve(self.db, dict(persons=["Shackleton", "Wild"], year_from=1915, year_to=1915, place="weddell sea",
                                       action="abandon ship", parent_event="Q-ITAE", spans=[["en:South/4", 0, 100]]), status="published")

    def v(self, **kw):
        return registry.check(self.db, dict(BASE, **kw))[0]

    def test_duplicates(self):
        self.assertEqual(self.v(title="范增之去"), "duplicate")                                       # retitled
        self.assertEqual(self.v(persons=["Chen Ping", "Fan Zeng"], spans=[["zh:史記/卷056", 1100, 1150]]), "duplicate")  # English names
        self.assertEqual(self.v(persons=["陳平", "項羽"], place="滎陽"), "duplicate")                # traditional
        self.assertEqual(self.v(persons=["亚父", "项王"]), "duplicate")                               # aliases only
        self.assertEqual(registry.check(self.db, dict(persons=["Washington"], year_from=1783, year_to=1783, place="x",
                                                      action="y", event_qid="Q-OLD", spans=[["en:Shaw", 1, 2]]))[0], "duplicate")  # QID redirect

    def test_not_falsely_rejected(self):
        self.assertEqual(registry.check(self.db, dict(persons=["Shackleton", "Worsley"], year_from=1916, year_to=1916, place="southern ocean",
                                                      action="boat voyage", parent_event="Q-ITAE", spans=[["en:South/9", 0, 100]]))[0], "distinct")
        self.assertEqual(self.v(persons=["刘邦", "纪信"], action="纪信假扮汉王出降，汉王从西门出逃", spans=[["zh:史記/卷007", 8000, 8200]]), "distinct")

    def test_other_work_paraphrase_goes_to_review(self):
        self.assertEqual(self.v(persons=["陈平", "范增"], action="陈平用金离间项羽与范增", spans=[["zh:資治通鑑/卷010", 30, 60]]), "review")

    def test_prepared_items_count_and_race_is_blocked(self):
        eid, _ = registry.reserve(self.db, dict(BASE, action="陈平离楚投汉", persons=["陈平"], spans=[["zh:史記/卷056", 100, 300]]), status="prepared")
        self.assertIsNotNone(eid)
        self.assertEqual(self.v(persons=["Chen Ping"], spans=[["zh:史記/卷056", 150, 160]]), "duplicate")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO episode(episode_id,status,core_span,spans,persons) VALUES('race','prepared','zh:史記/卷056@100','[]','[]')")

    def test_short_name_recall(self):
        self.assertTrue(registry.recall(self.db, "陳平"))
        self.assertEqual(self.db.execute("SELECT count(*) FROM episode WHERE instr(search_text,'陈平')>0").fetchone()[0], 1)

    def test_rebuild_from_content_gives_same_verdicts(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.json"
            p.write_text(json.dumps({"episode_id": "ep-x", "title": {"zh": "陈平反间"}, "category": "china_ancient", "status": "published",
                                     "episode": {k: v for k, v in BASE.items() if k != "title"}}, ensure_ascii=False))
            db2 = mk(); self.assertEqual(registry.rebuild_from_content(db2, [p]), 1)
            self.assertEqual(registry.check(db2, dict(BASE, title="x"))[0], "duplicate")


CANDIDATE = {
    "candidate_id": "cand-test", "category": "china_ancient", "title_hint": "测试",
    "episode": {"persons": ["陈平"], "year_from": -205, "year_to": -205, "place": "修武", "action": "陈平降汉"},
    "sources": [{"id": "A-SJ56", "adapter": "wikisource_render", "ref": "zh:史記/卷056", "title": "史記·陳丞相世家", "basis": "shiji", "must_contain": ["陳平"]}],
    "excerpts": [["T-E1", "A-SJ56", "平遂至修武降漢", "愈益幸平。", "陳丞相世家"]],
    "single_basis_disclosed": True, "brief": "测试"}


def refusing_call(prompt, timeout_s=0, **kw):
    refusing_call.n += 1
    return {"rc": 0, "killed": None, "wall_s": 6.0, "prompt_bytes": len(prompt), "prompt_chars": len(prompt), "out_bytes": 60, "out_chars": 60,
            "stderr": "", "text": "The request was rejected because it was considered high risk"}
refusing_call.n = 0


def fake_call_factory(zh_ok=True, timeout=False):
    zh = {"title": "陈平降汉", "dek": "d", "sections": [{"id": i, "heading": i, "paras": [{"t": "陈平降汉。", "kind": "record", "ev": ["T-E1"]}]} for i in ("hook", "context", "story", "analysis")] +
          [{"id": "today", "heading": "t", "paras": [{"t": "现代一", "kind": "modern", "ev": []}, {"t": "现代二", "kind": "modern", "ev": []}]},
           {"id": "limits", "heading": "l", "paras": [{"t": "边界", "kind": "uncertainty", "ev": ["T-E1"]}]}],
          "reflection": {"type": "相信谁", "scenario": "s", "question": "q", "example": {"assumptions": "a", "steps": "b", "alternative": "c"}},
          "uncertainty_note": "u"}
    en = json.loads(json.dumps(zh).replace("陈平降汉。", "Chen Ping went over to Han.").replace("现代一", "Modern one").replace("现代二", "Modern two")
                    .replace("边界", "Limits").replace('"t": "陈平降汉"', '"t": "x"'))
    en["title"] = "Chen Ping defects"
    calls = []
    def call(prompt, timeout_s=0, **kw):
        calls.append(timeout_s)
        if timeout:
            return {"rc": -15, "killed": "timeout", "wall_s": timeout_s, "prompt_bytes": len(prompt), "prompt_chars": len(prompt), "out_bytes": 0, "out_chars": 0, "stderr": "", "text": ""}
        if "事实编辑" in prompt:
            out = {"edits": [], "dispositions": []}
        elif "English edition says the same" in prompt or "事实审稿人" in prompt:
            out = {"issues": [], "overall": "ok"}
        else:
            out = zh if "【编辑简报】" in prompt else en
        text = json.dumps(out, ensure_ascii=False)
        return {"rc": 0, "killed": None, "wall_s": 0.1, "prompt_bytes": len(prompt), "prompt_chars": len(prompt), "out_bytes": len(text), "out_chars": len(text), "stderr": "", "text": text}
    call.calls = calls
    return call


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); self.cache = Path(self.td.name) / "cache"; self.cache.mkdir()
        shutil.copy(ROOT / "tests/fixtures/A-SJ56.txt", self.cache / "A-SJ56.txt")      # public-domain Shiji text, committed
        (self.cache / "A-SJ56.meta.json").write_text(json.dumps({"status": "evidence_usable", "source_id": "A-SJ56"}))
        self.db = state.connect(Path(self.td.name) / "s.sqlite"); registry.init(self.db, ALIASES)

    def tearDown(self):
        self.td.cleanup()

    def prep(self, c, call):
        return pipeline.prepare(c, self.db, call=call, workdir=Path(self.td.name) / c["candidate_id"], cache=self.cache)

    def test_good_candidate_reaches_inventory(self):
        r = self.prep(CANDIDATE, fake_call_factory()); self.assertEqual(r["outcome"], "pending_review", r)
        self.assertIn("awaiting editor stage", r["reason"])                       # clean drafts still need the editor stage
        self.assertEqual(pipeline.inventory(self.db)["schedulable_total"], 0)
        wd = Path(self.td.name) / CANDIDATE["candidate_id"]
        rec = editor.edit(wd, call=fake_call_factory()); self.assertEqual(rec["outcome"], "admissible", rec["remaining"])
        self.assertEqual([x["round"] for x in rec["rounds"]], [0])                # no issues: one review + parity bound to the content
        a = editor.admit_with_record(self.db, wd / "edited.json", wd / "evidence.json", rec); self.assertTrue(a["admitted"], a)
        self.assertEqual(pipeline.inventory(self.db)["schedulable_by_category"]["china_ancient"], 1)
        self.assertRegex(r["code_rev"], r"^([0-9a-f]{7,}|unknown)$")       # which code judged it
        log = [json.loads(l) for l in (Path(self.td.name) / CANDIDATE["candidate_id"] / "calls.jsonl").read_text().splitlines()]
        self.assertEqual([(x["step"], x["json_ok"]) for x in log], [("draft_zh", True), ("review_zh", True), ("en", True), ("rereview_r0", True), ("parity_r0", True)])

    def test_missing_source_goes_pending_and_others_continue(self):
        bad = json.loads(json.dumps(CANDIDATE)); bad["candidate_id"] = "cand-bad"; bad["excerpts"][0][2] = "不存在的锚点"
        self.assertEqual(self.prep(bad, fake_call_factory())["outcome"], "pending_review")
        self.assertEqual(self.prep(CANDIDATE, fake_call_factory())["outcome"], "pending_review")

    def test_duplicate_candidate_rejected(self):
        self.prep(CANDIDATE, fake_call_factory())
        dup = json.loads(json.dumps(CANDIDATE)); dup["candidate_id"] = "cand-dup"; dup["episode"]["persons"] = ["陳平"]
        self.assertEqual(self.prep(dup, fake_call_factory())["outcome"], "rejected")

    def test_rerun_after_crash_reuses_saved_model_outputs(self):
        call = fake_call_factory(); wd = Path(self.td.name) / CANDIDATE["candidate_id"]
        pipeline.run_model_steps(CANDIDATE, {"sources": {}, "excerpts": []}, wd if wd.mkdir(parents=True, exist_ok=True) is None else wd, call=call)
        n = len(call.calls); self.assertEqual(n, 3)
        r = self.prep(CANDIDATE, call); self.assertEqual(r["outcome"], "pending_review"); self.assertEqual(len(call.calls), n)   # no new model calls

    def test_list_valued_fields_are_coerced(self):
        o = pipeline.merge({"title": ["a", "b"], "dek": "d", "sections": [], "reflection": {"type": "t", "scenario": "s", "question": "q",
                            "example": {"assumptions": ["x", "y"], "steps": "s", "alternative": "a"}}, "uncertainty_note": "u"},
                           {"title": "T", "sections": [], "reflection": {}, "uncertainty_note": "U"})
        self.assertEqual(o["reflection"]["example"]["assumptions"]["zh"], "x\ny"); self.assertEqual(o["title"]["zh"], "a\nb")

    def test_review_fix_issue_sends_to_pending(self):
        base = fake_call_factory()
        def call(prompt, timeout_s=0, **kw):
            r = base(prompt, timeout_s=timeout_s)
            if "事实审稿人" in prompt:
                r["text"] = json.dumps({"issues": [{"severity": "fix", "section": "story", "para": 0, "problem": "反了"}], "overall": "x"}, ensure_ascii=False)
            return r
        r = self.prep(CANDIDATE, call); self.assertEqual(r["outcome"], "pending_review"); self.assertIn("fix/block", r["reason"])

    def test_provider_refusal_goes_pending_without_retry(self):
        refusing_call.n = 0; r = self.prep(CANDIDATE, refusing_call)
        self.assertEqual(r["outcome"], "pending_review"); self.assertIn("provider refusal", r["reason"]); self.assertEqual(refusing_call.n, 1)
        log = [json.loads(l) for l in (Path(self.td.name) / CANDIDATE["candidate_id"] / "calls.jsonl").read_text().splitlines()]
        self.assertTrue(log[0]["provider_refusal"]); self.assertFalse(log[0]["json_ok"])        # logged after parsing

    def test_refusal_at_review_is_named_not_review_missing(self):
        base = fake_call_factory()
        def call(prompt, timeout_s=0, **kw):
            r = base(prompt, timeout_s=timeout_s)
            if "事实审稿人" in prompt:
                r["text"] = "The request was rejected because it was considered high risk"
            return r
        r = self.prep(CANDIDATE, call)
        self.assertEqual(r["outcome"], "pending_review"); self.assertIn("provider refusal at review_zh", r["reason"])

    def test_model_timeout_goes_pending_without_second_full_timeout(self):
        call = fake_call_factory(timeout=True); r = self.prep(CANDIDATE, call)
        self.assertEqual(r["outcome"], "pending_review"); self.assertEqual(len(call.calls), 1)


if __name__ == "__main__":
    unittest.main()

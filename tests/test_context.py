"""Source-context review (context.py) on small LABELLED SYNTHETIC sources built here: the decisive answer just past an
excerpt, paraphrased zh/en absence wording, a scoped statement that really is supported, missing / truncated units, the
search round for long sources, and a clean record that stops verifying when evidence, source text or content change.
The reviewer is a scripted fake; the real run is recorded in docs/AFK_TEST_AND_BOOKS_REPORT.md."""
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import context, evidence, editor

SRC = ("起之為人，猜忍人也。夫魯小國，而有戰勝之名，則諸侯圖魯矣。且魯衛兄弟之國也，而君用起，則是棄衛。」"
       "魯君疑之，謝吳起。吳起於是聞魏文侯賢，欲事之。")


def reply(obj):
    t = json.dumps(obj, ensure_ascii=False)
    return {"rc": 0, "killed": None, "wall_s": 0.1, "text": t, "meta": {"usage": {"output_tokens": 5}}}


def article(*zh_sentences, en=""):
    o = {"edition_id": "cand-t", "title": {"zh": "辞婚", "en": "A refused marriage"}, "dek": {"zh": "", "en": ""},
         "sections": [{"id": "story", "heading": {"zh": "经过", "en": "What happened"},
                       "paras": [{"kind": "record", "ev": ["T-E1"], "zh": "".join(zh_sentences), "en": en}]}],
         "reflection": {"scenario": {"zh": "", "en": ""}, "question": {"zh": "", "en": ""}, "example": {}},
         "uncertainty_note": {"zh": "", "en": ""}}
    o["content_sha256"] = editor.sha(o)
    return o


class Base(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp()); self.cache = self.td / "cache"; self.cache.mkdir()
        (self.cache / "S-T.txt").write_text(SRC, encoding="utf-8")
        self.ev, err = evidence.build([["T-E1", "S-T", "起之為人", "則是棄衛。」", "卷65"]],
                                      {"S-T": {"status": "evidence_usable", "cjk": True, "title": "史記 卷065（fixture）"}}, self.cache)
        self.assertEqual(err, [])

    def review(self, o, script, ev=None):
        calls = []
        def call(prompt, timeout_s=0, **kw):
            calls.append(prompt)
            obj = script(prompt, len(calls))
            # These fixtures focus on claim dispositions; include the required episode array.
            obj.setdefault("episode", [])
            return reply(obj)
        rec, new = context.review(o, ev or self.ev, self.cache, self.td / "out", call=call, cid="cand-t")
        return rec, new, calls

    @staticmethod
    def claims(prompt, **by_sentence):
        flagged = json.JSONDecoder().raw_decode(prompt.split("【待核断言】\n", 1)[1])[0] if "【待核断言】" in prompt else []
        return [dict({"id": f["id"], "verdict": "not_a_source_claim", "source_ids": ["S-T"], "scope": "卷65全篇"}, **by_sentence.get(f["sentence"], {}))
                for f in flagged]


class DecisiveAnswer(Base):
    CLAIM = "这里所据的原文止于这段进言，没有记载鲁君听后如何处置。"

    def test_answer_just_past_the_excerpt_blocks_and_is_cut_into_the_pack(self):
        o = article("鲁国有人进言。", self.CLAIM, en="The source does not say how the ruler responded.")
        rec, new, calls = self.review(o, lambda p, n: {"episode": [{"source_id": "S-T", "outcome": "鲁君疑而辞退吴起", "quote": "魯君疑之，謝吳起", "in_evidence": False}],
            "additions": [{"source_id": "S-T", "start": "魯君疑之", "end": "欲事之。", "why": "结局紧接摘录"}], "context_issues": [],
            "claims": self.claims(p, **{self.CLAIM: {"verdict": "contradicted", "quote": {"source_id": "S-T", "quote": "鲁君疑之，谢吴起"}},
                                        "The source does not say how the ruler responded.": {"verdict": "contradicted",
                                                                                            "quote": {"source_id": "S-T", "quote": "魯君疑之，謝吳起"}}})})
        self.assertIn("魯君疑之，謝吳起", calls[0])                                     # the reviewer read past the cut
        self.assertEqual(rec["units"]["S-T"]["status"], "complete")
        self.assertEqual(rec["outcome"], "needs_work")
        self.assertEqual([a["id"] for a in rec["additions"]], ["T-E2"])
        self.assertEqual(new["excerpts"][-1]["quote"], "魯君疑之，謝吳起。吳起於是聞魏文侯賢，欲事之。")
        self.assertNotEqual(rec["evidence_sha256"], editor.sha(self.ev))
        self.assertTrue(any("contradicted" in b for b in rec["blocking"]))
        self.assertTrue(context.record_problems(rec, o, self.ev, self.cache))
        iss = context.issues_for_editor(rec)
        self.assertTrue(any("鲁君疑之，谢吴起" in i["problem"] and "不要改成“摘录未写”" in i["problem"] for i in iss))

    def test_narrowing_to_the_excerpt_is_flagged_again_and_needs_its_own_verdict(self):
        narrowed = "本文所据摘录没有写鲁君如何处置。"
        self.assertEqual([f["sentence"] for f in context.absence_claims(article(narrowed))], [narrowed])
        o = article(narrowed)
        rec, _, _ = self.review(o, lambda p, n: {"additions": [], "context_issues": [], "claims": self.claims(p, **{narrowed: {
            "verdict": "contradicted", "quote": {"source_id": "S-T", "quote": "謝吳起"}}})})
        self.assertEqual(rec["outcome"], "needs_work")

    def test_a_contradiction_needs_a_real_quote(self):
        o = article(self.CLAIM)
        rec, _, calls = self.review(o, lambda p, n: {"additions": [], "context_issues": [], "claims": self.claims(p, **{self.CLAIM: {
            "verdict": "contradicted", "quote": {"source_id": "S-T", "quote": "魯君大喜，厚賞吳起"}}})})
        self.assertEqual(len(calls), 2); self.assertEqual(rec["outcome"], "failed")       # schema retry once, then failed
        self.assertIn("verbatim quote", calls[1])


class Wording(unittest.TestCase):
    def test_paraphrased_absence_wording_zh_and_en(self):
        yes_zh = ["史书对此只字未提。", "他为何离开，已不得而知。", "记述止于此。", "信中并未说明理由。", "原文没有交代落实得如何。", "详情不详。"]
        no_zh = ["他没有回答。", "他未能成功。", "吴起离开了魏国。"]
        yes_en = ["The chronicle is silent on his motive.", "No account survives of the meeting.", "We do not know what he said.",
                  "The letter does not explain why.", "How it was carried out is not recorded."]
        no_en = ["Grant did not stop.", "He left Wei for Chu."]
        o = article(*yes_zh, *no_zh, en=" ".join(yes_en + no_en))
        got = {(f["lang"], f["sentence"]) for f in context.absence_claims(o)}
        self.assertEqual(got, {("zh", s) for s in yes_zh} | {("en", s) for s in yes_en})


class Scope(Base):
    def test_scoped_supported_statement_on_a_complete_unit_is_clean(self):
        s = "这一篇没有写吴起为自己辩解。"
        o = article(s)
        rec, new, _ = self.review(o, lambda p, n: {"additions": [], "context_issues": [], "claims": self.claims(p, **{s: {"verdict": "supported"}})})
        self.assertEqual((rec["outcome"], rec["blocking"]), ("clean", []))
        self.assertEqual(rec["units"]["S-T"]["spans"], [[0, len(evidence.normalise(SRC, True))]])
        self.assertEqual(context.record_problems(rec, o, self.ev, self.cache), [])

    def test_missing_unit_never_verifies_absence(self):
        s = "这一篇没有写吴起为自己辩解。"; o = article(s)
        (self.cache / "S-T.txt").unlink()
        rec, _, calls = self.review(o, lambda p, n: {"additions": [], "context_issues": [], "claims": self.claims(p, **{s: {"verdict": "supported"}})})
        self.assertIn("没有可读文本", calls[0]); self.assertEqual(rec["units"]["S-T"]["status"], "missing")
        self.assertEqual(rec["claims"][0]["verdict"], "unresolved"); self.assertEqual(rec["outcome"], "needs_work")

    def test_truncated_unit_never_verifies_absence_and_search_round_is_bounded(self):
        far = "王錯者，魏之賢臣也，" * 40                                                    # a long synthetic source
        (self.cache / "S-T.txt").write_text(far + SRC + far * 30 + "吳起曰：臣無罪。" + far * 30, encoding="utf-8")
        ev, _ = evidence.build([["T-E1", "S-T", "起之為人", "則是棄衛。」", "卷65"]],
                               {"S-T": {"status": "evidence_usable", "cjk": True, "title": "long fixture"}}, self.cache)
        s = "这一篇没有写吴起为自己辩解。"; o = article(s)
        old = dict(context.CAP); context.CAP.update({True: 1400})
        try:
            def script(p, n):
                if n == 1:                                                            # windows: ask for a search
                    self.assertNotIn("臣無罪", p); self.assertIn("則是棄衛", p)                # the excerpt itself is always in view
                    return {"additions": [], "context_issues": [], "search": ["吳起曰"], "claims": self.claims(p, **{s: {"verdict": "needs_search"}})}
                self.assertIn("臣無罪", p)                                             # the search window is in front of the reviewer
                return {"additions": [], "context_issues": [], "claims": self.claims(p, **{s: {"verdict": "contradicted",
                        "quote": {"source_id": "S-T", "quote": "吳起曰：臣無罪"}}})}
            rec, _, calls = self.review(o, script, ev)
            self.assertEqual(len(calls), 2); self.assertEqual(rec["search"]["terms"], ["吳起曰"])
            self.assertEqual(rec["outcome"], "needs_work")
            context.CAP.update({True: 1400})                                          # no search this time: windows trimmed
            rec, _, _ = self.review(o, lambda p, n: {"additions": [], "context_issues": [], "claims": self.claims(p, **{s: {"verdict": "supported"}})}, ev)
            self.assertEqual(rec["units"]["S-T"]["status"], "truncated")
            self.assertEqual(rec["claims"][0]["verdict"], "unresolved"); self.assertIn("truncated", rec["claims"][0]["downgraded"])
        finally:
            context.CAP.clear(); context.CAP.update(old)


class Binding(Base):
    def test_clean_record_stops_verifying_when_evidence_source_or_content_change(self):
        s = "这一篇没有写吴起为自己辩解。"; o = article(s)
        rec, _, _ = self.review(o, lambda p, n: {"additions": [], "context_issues": [], "claims": self.claims(p, **{s: {"verdict": "supported"}})})
        self.assertEqual(context.record_problems(rec, o, self.ev, self.cache), [])
        ev2 = json.loads(json.dumps(self.ev)); ev2["excerpts"].append(dict(ev2["excerpts"][0], id="T-E2"))
        self.assertIn("context review is for different evidence", context.record_problems(rec, o, ev2, self.cache))
        o2 = article(s, "另有记载不详。")
        p = context.record_problems(rec, o2, self.ev, self.cache)
        self.assertIn("context review is for different content", p); self.assertTrue(any("另有记载不详" in x for x in p))
        (self.cache / "S-T.txt").write_text(SRC + "後記。", encoding="utf-8")
        self.assertIn("source S-T changed or missing since the context review", context.record_problems(rec, o, self.ev, self.cache))
        self.assertEqual(context.record_problems(None, o, self.ev, self.cache), ["no source-context review for this content"])


class SourceCheckWordingAndSchema(unittest.TestCase):
    def test_snow_independent_check_claims_are_triaged_in_limits_and_note(self):
        zh = "本篇证据中没有当时卫生部门或他人的独立核查。"
        en = "The evidence used here contains no independent check by a health authority or anyone else at the time."
        o = article(zh, en=en)
        o["sections"][0]["id"] = "limits"
        o["uncertainty_note"] = {"zh": zh, "en": en}
        got = {(f["path"], f["lang"]) for f in context.absence_claims(o)}
        self.assertEqual(got, {("sections.limits.0", "zh"), ("sections.limits.0", "en"),
                               ("uncertainty_note", "zh"), ("uncertainty_note", "en")})

    def test_positive_official_returns_and_unrelated_negation_are_not_absence(self):
        o = article("登记员的后续报表得到公布。", "他没有回答。",
                    en="The later returns were published. Grant did not stop.")
        self.assertEqual(context.absence_claims(o), [])

    def test_further_reading_what_and_access_are_not_outside_the_review(self):
        o = article("正常叙事。")
        o["further_reading"] = [{"what": {"zh": "没有第三方核查。", "en": ""},
                                 "access": {"zh": "", "en": "No independent verification is available."}}]
        self.assertEqual({f["path"] for f in context.absence_claims(o)},
                         {"further_reading.0.what", "further_reading.0.access"})

    def test_empty_or_partial_review_is_invalid_even_when_no_claim_is_flagged(self):
        validate = context.reply_schema([], {}, {}, False)
        for bad in ({}, {"claims": []}, {"claims": [], "context_issues": []}):
            with self.subTest(reply=bad):
                self.assertTrue(validate(bad))

    def test_non_object_rows_and_duplicate_verdicts_are_invalid(self):
        validate = context.reply_schema([{"id": "A1"}], {"S": {}}, {}, False)
        base = {"episode": [], "additions": [], "claims": [], "context_issues": []}
        for key in base:
            bad = dict(base, **{key: [None]})
            with self.subTest(field=key):
                self.assertTrue(validate(bad))
        claim = {"id": "A1", "verdict": "not_a_source_claim"}
        self.assertTrue(validate(dict(base, claims=[claim, dict(claim)])))

    def test_supported_verdict_requires_known_source_identifiers(self):
        validate = context.reply_schema([{"id": "A1"}], {"S": {}}, {}, False)
        base = {"episode": [], "additions": [], "context_issues": []}
        for source_ids in ("S", ["unread-source"], [], [None]):
            claim = {"id": "A1", "verdict": "supported", "scope": "specified unit", "source_ids": source_ids}
            with self.subTest(source_ids=source_ids):
                self.assertTrue(validate(dict(base, claims=[claim])))

    def test_explicit_review_with_no_findings_remains_valid(self):
        self.assertEqual(context.reply_schema([], {}, {}, False)(
            {"episode": [], "additions": [], "claims": [], "context_issues": []}), [])


if __name__ == "__main__":
    unittest.main()

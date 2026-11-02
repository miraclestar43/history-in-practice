"""原文精选 (2026-11-02): the model picks paragraph numbers; the program takes the text from the saved book; guide,
notes and the AI translation are the editor's; a review fix may change those but never the original. The model is fake."""
import hashlib, json, os, re, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import library, excerpt, render, state, registry, mix, site_export, publish
from history_in_practice.final_edit import send_problems, current_eligibility

PARAS = ["CHAPTER I", "THE LETTER"] + [f"Paragraph {i}: in 1863 I received a letter from my friend Chang, who said, it was rumoured, that the Viceroy wished to see me. Word {i}." for i in range(1, 50)]


def fake(answers):
    def call(prompt, timeout_s=0, **kw):
        step = ("select" if "选段编辑" in prompt else "guide" if "导读、注释、人名" in prompt else "translate" if prompt.startswith("Task: translate")
                else "reflect_review" if "只审本期文后" in prompt else "reflect" if "为一期“原文精选”写文后" in prompt else "review")
        if step not in answers and step.startswith("reflect"):
            ans = {"reflect": {"questions": {"zh": ["他为什么这样选？"], "en": ["Why did he choose so?"]}, "angle": {"zh": "一种理解。", "en": "One reading."}},
                   "reflect_review": {"issues": [], "reading": "ok"}}[step]
            return {"rc": 0, "killed": None, "wall_s": 0.1, "prompt_bytes": 1, "out_bytes": 1, "text": json.dumps(ans, ensure_ascii=False), "meta": {"model": "fake-model"}}
        ans = answers[step]; ans = ans(prompt) if callable(ans) else ans
        return {"rc": 0, "killed": None, "wall_s": 0.1, "prompt_bytes": 1, "out_bytes": 1, "text": json.dumps(ans, ensure_ascii=False), "meta": {"model": "fake-model"}}
    return call


class Excerpt(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); root = Path(self.td.name); os.environ["HIP_DATA_DIR"] = str(root / "data")
        files = root / "data/books/files"; files.mkdir(parents=True)
        data = ("\n\n".join(PARAS) + "\n").encode()
        (files / "BK-X.txt").write_bytes(data)
        (root / "data/books/manifest.json").write_text(json.dumps({"files": [{"book_id": "BK-X", "path": "BK-X.txt", "format": "txt",
                                                                             "file_sha256": hashlib.sha256(data).hexdigest()}]}))
        self.old = library.LIB; library.LIB = root / "library.json"
        library.save({"books": [{"book_id": "BK-X", "title": "My Life", "author": "Someone", "author_en": "Someone", "author_zh": "某人",
                                 "language": "en", "genre": "memoir", "categories": ["china_modern"], "level": "acquired", "rights": "public_domain",
                                 "themes": ["人物传记"]}]})
        library.ingest("BK-X", verified="test"); self.out = root / "out"

    def tearDown(self):
        library.LIB = self.old; os.environ.pop("HIP_DATA_DIR"); self.td.cleanup()

    def test_text_comes_from_the_book_and_only_the_editors_text_changes(self):
        def translate(prompt):
            ids = [int(x) for x in re.findall(r"^\[P(\d+)\]", prompt.split("【Excerpt】", 1)[1], re.M)]
            return {"paras": [{"p": k, "text": f"第{k}段译文：1863年，我收到朋友张某的信，据说总督想见我。"} for k in ids], "title_check": "ok"}
        ans = {"select": {"start": 2, "end": 12, "omit": [[6, 7]], "title": {"zh": "一封信", "en": "A Letter"}, "why": "w", "standalone": "s",
                          "context_needed": [], "omit_check": "两段重复"},
               "guide": {"dek": {"zh": "一封信", "en": "A letter"}, "intro": {"zh": "导读。", "en": "Intro."},
                         "names": [{"orig": "Chang", "zh": "张某", "en": "Chang", "certain": False}],
                         "notes": [{"para": 3, "term": "Viceroy", "zh": "总督。", "en": "The governor-general."}], "after": None,
                         "continue": {"zh": "下一章。", "en": "Next chapter."}},
               "translate": translate,
               "review": {"issues": [{"id": "X1", "area": "translation", "severity": "fix", "where": "tr.P3", "problem": "漏译“据说”", "proposed": "修正后的译文。"},
                                     {"id": "X2", "area": "selection", "severity": "fix", "where": "orig.P4", "problem": "改原文", "proposed": "Rewritten original."}],
                          "reading": "自然。"}}
        o = excerpt.run("BK-X", (0, len(PARAS)), "ex-1", "china_modern", call=fake(ans), out_root=self.out)
        self.assertEqual(o["kind"], "excerpt"); self.assertEqual(o["checks"], [])
        self.assertEqual([x["p"] for x in o["passage"]], [2, 3, 4, 5, 8, 9, 10, 11, 12])
        self.assertTrue(o["passage"][4]["gap_before"])                                    # the omission is marked
        self.assertTrue(all(x["en"] == PARAS[x["p"]] for x in o["passage"]))               # the original, byte for byte
        self.assertEqual(next(x for x in o["passage"] if x["p"] == 3)["zh"], "修正后的译文。")   # translation fix applied
        self.assertTrue(any(i["id"] == "X2" for i in o["open_issues"]))                    # never applied to the original
        o2 = json.loads(json.dumps(o)); o2["passage"][0]["en"] += " (edited)"
        self.assertTrue(any("differs from the source" in p for p in excerpt.checks(o2, excerpt.book("BK-X")[1], None, False)))
        o3 = json.loads(json.dumps(o)); o3["passage"][4]["gap_before"] = False
        self.assertTrue(any("without a 〔中略〕" in p for p in excerpt.checks(o3, excerpt.book("BK-X")[1], None, False)))
        o["edition_date"] = "2026-11-03"; render.finalize(o)
        h, t = render.email_html(o, "https://x"), render.email_text(o, "https://x")
        for x in ("AI 译文", "原文", "〔中略〕", "某人 著", "在网页阅读"):
            self.assertIn(x, h)
        self.assertLess(h.index("在网页阅读"), h.index("导读"))
        self.assertTrue(any(l.startswith("Read in English") for l in t.splitlines()[:7]))           # links right after the title
        tpl = (Path(__file__).resolve().parents[1] / "src/history_in_practice/templates/history_index.html").read_text()
        self.assertIn('if (o.kind === "excerpt") return renderExcerpt(o);', tpl)
        meta, text = render.search_index([dict(o, status="published")])
        self.assertIn("张某", meta["items"][0]["people"]); self.assertIn("My Life", meta["items"][0]["books"])

    def test_long_chinese_paragraphs_display_in_sentence_pieces_that_join_back(self):
        para = "".join(f"第{i}句话写一件事，写得比较长，要读一会儿才能读完。" for i in range(1, 15)) + "他说：“我们走吧。到了那边再说。”众人点头。"
        parts = excerpt.display_parts(para)
        self.assertGreater(len(parts), 1); self.assertEqual("".join(parts), para)            # display only: the paragraph is intact
        self.assertTrue(all(x.endswith(("。", "”", "！", "？")) for x in parts))               # cut only after a full sentence
        self.assertIsNone(excerpt.display_parts("短段落。"))
        o = {"passage": [{"p": 1, "zh": para, "zh_parts": parts[:-1] + [parts[-1] + "多"]}], "notes": [], "intro": {"zh": "a", "en": "b"},
             "work": {"original_language": "en"}}
        o["passage"][0]["en"] = PARAS[1]
        self.assertIn("P1: display parts do not join back to the paragraph", excerpt.checks(o, excerpt.book("BK-X")[1], None, False))

    def good_answers(self):
        def translate(prompt):
            ids = [int(x) for x in re.findall(r"^\[P(\d+)\]", prompt.split("【Excerpt】", 1)[1], re.M)]
            return {"paras": [{"p": k, "text": f"第{k}段译文：1863年，我收到朋友张某的信，据说总督想见我。"} for k in ids], "title_check": "ok"}
        return {"select": {"start": 2, "end": 12, "omit": [], "title": {"zh": "一封信", "en": "A Letter"}, "why": "w", "standalone": "s"},
                "guide": {"dek": {"zh": "一封信", "en": "A letter"}, "intro": {"zh": "导读。", "en": "Intro."}, "names": [], "notes": [],
                          "continue": {"zh": "下一章。", "en": "Next chapter."}, "episode": {"year_from": 1863, "year_to": 1863, "place": "上海", "action": "收到一封信"}},
                "translate": translate, "review": {"issues": [], "reading": "自然。"}}

    def test_admission_schedule_send_gate_and_site_verify(self):
        from history_in_practice.config import REPO
        o = excerpt.run("BK-X", (0, len(PARAS)), "ex-adm", "china_modern", call=fake(self.good_answers()), out_root=self.out)
        self.assertEqual((o["checks"], o["open_issues"]), ([], [])); self.assertEqual(o["reflect"]["questions"]["zh"], ["他为什么这样选？"])
        db = state.connect(Path(self.td.name) / "s.sqlite"); registry.init(db, {}); mix.init(db)
        path = self.out / "ex-adm" / "excerpt.json"
        a = excerpt.admit(db, path); self.assertTrue(a["admitted"], a)
        self.assertEqual(state.get(db, "ex-adm")["status"], "checked"); self.assertTrue(state.get(db, "ex-adm")["approval"].startswith("excerpt-editor:"))
        self.assertEqual(current_eligibility(db, "ex-adm")[0], [])
        self.assertFalse(excerpt.admit(db, path)["admitted"])                            # once only
        bad = json.loads(path.read_text()); bad["passage"][0]["en"] += " (edited)"; path.write_text(json.dumps(bad))
        self.assertTrue(current_eligibility(db, "ex-adm")[0])                             # the admitted file must stay the source text
        path.write_text(json.dumps(o, ensure_ascii=False))
        ed = dict(state.get(db, "ex-adm"), edition_date="2026-11-03")
        with tempfile.TemporaryDirectory() as cd:
            arch = json.loads(publish.archive(db, ed, Path(cd)).read_text())
        self.assertEqual(send_problems(db, arch), [])                                     # the archived copy may be sent
        arch2 = json.loads(json.dumps(arch)); arch2["passage"][1]["zh"] = "改过的译文"
        self.assertIn("passage differs from the admitted article", send_problems(db, arch2))
        with tempfile.TemporaryDirectory() as sd:
            site_export.export([arch], Path(sd))
            live = json.loads(next(Path(sd).glob("data/history/2026/11/*.json")).read_text())
            self.assertFalse({"review", "calls", "selection", "admitted_from", "checks"} & set(live))     # internal records stay off the site
            fetch = lambda url, timeout=20: (200, "application/json", (Path(sd) / url.split("x.test/", 1)[1]).read_bytes())
            self.assertEqual(site_export.verify(arch, "https://x.test", fetch=fetch), (True, []))

    def test_mix_prefers_excerpts_and_nightly_supply_tops_up(self):
        story = mix.item("st-1", "china_modern", {"title": {"zh": "旧故事"}}, 1.0); ex = mix.item("ex-9", "china_modern", {"kind": "excerpt", "title": {"zh": "原文"}}, 9.0)
        seq = mix.plan([story, ex], 1, 0)
        self.assertEqual(seq[0]["edition_id"], "ex-9"); self.assertIn("原文精选优先", seq[0]["reason"])
        a1 = mix.item("ex-a1", "china_ancient", {"kind": "excerpt", "work": {"book_id": "BK-A"}}, 1.0)
        a2 = mix.item("ex-a2", "china_modern", {"kind": "excerpt", "work": {"book_id": "BK-A"}}, 2.0)
        b1 = mix.item("ex-b1", "china_modern", {"kind": "excerpt", "work": {"book_id": "BK-B"}}, 3.0)
        o1 = mix.item("st-o", "world", {"title": {"zh": "x"}}, 1.0); o2 = mix.item("st-o2", "us", {"title": {"zh": "y"}}, 1.0)
        seq = [x["edition_id"] for x in mix.plan([a1, a2, b1, o1, o2], 5, 0)]
        self.assertNotEqual(seq.index("ex-a2") - seq.index("ex-a1"), 1)                   # not the same book twice in a row
        db = state.connect(Path(self.td.name) / "s2.sqlite"); registry.init(db, {})
        old = excerpt.ADMIT_ROOT; excerpt.ADMIT_ROOT = self.out / "admitted"
        try:
            rs = excerpt.supply(db, ["china_modern"], target=1, max_runs=2, call=fake(self.good_answers()), today="20261103")
        finally:
            excerpt.ADMIT_ROOT = old
        self.assertEqual([r["outcome"] for r in rs], ["admitted"])                         # stops at the target
        self.assertEqual(excerpt.supply(db, ["china_modern"], target=1)[0]["outcome"], "enough")
        self.assertTrue(any(a["outcome"] == "admitted" for a in excerpt.attempts()))
        self.assertFalse([u for u in excerpt.units_open() if u["unit"] == rs[0]["edition_id"].rsplit("-u", 1)[1] and u["book_id"] == "BK-X"])

    def test_excerpts_only_plan_never_uses_stories_and_the_band_does_not_stop_it(self):
        old = mix.EXCERPTS_ONLY; mix.EXCERPTS_ONLY = True
        try:
            pool = [mix.item(f"st-{k}", "world", {"title": {"zh": "旧故事"}}, 1.0) for k in range(3)] + \
                   [mix.item(f"ex-{k}", "china_modern", {"kind": "excerpt", "work": {"book_id": f"BK-{k}"}}, 2.0 + k) for k in range(6)]
            seq = mix.plan(pool, 7, 0)
            self.assertEqual([x["kind"] for x in seq], ["excerpt"] * 6)                    # six Chinese pieces in a row is fine
            self.assertFalse(any(x["edition_id"].startswith("st-") for x in seq))         # stories never stand in
        finally:
            mix.EXCERPTS_ONLY = old

    def test_reader_text_never_cites_paragraph_numbers(self):
        o = excerpt.run("BK-X", (0, len(PARAS)), "ex-p", "china_modern", call=fake(self.good_answers()), out_root=self.out)
        o["reflect"]["angle"]["zh"] = "对照前后两处（P6）。"
        self.assertTrue(any("paragraph numbers" in p for p in excerpt.checks(o, excerpt.book("BK-X")[1], None, False)))

    def test_model_never_supplies_the_original(self):
        ans = {"select": {"skip": "没有完整段落"}}
        self.assertEqual(excerpt.run("BK-X", (0, 20), "ex-2", "china_modern", call=fake(ans), out_root=self.out)["outcome"], "skipped")
        self.assertIn("不要输出原文文字", (Path(__file__).resolve().parents[1] / "src/history_in_practice/prompts/excerpt_select.md").read_text())


if __name__ == "__main__":
    unittest.main()

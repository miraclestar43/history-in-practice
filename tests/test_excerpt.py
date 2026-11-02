"""原文精选 (2026-11-02): the model picks paragraph numbers; the program takes the text from the saved book; guide,
notes and the AI translation are the editor's; a review fix may change those but never the original. The model is fake."""
import hashlib, json, os, re, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import library, excerpt, render

PARAS = ["CHAPTER I", "THE LETTER"] + [f"Paragraph {i}: in 1863 I received a letter from my friend Chang, who said, it was rumoured, that the Viceroy wished to see me. Word {i}." for i in range(1, 50)]


def fake(answers):
    def call(prompt, timeout_s=0, **kw):
        step = ("select" if "选段编辑" in prompt else "guide" if "导读、注释、人名" in prompt else "translate" if prompt.startswith("Task: translate")
                else "review")
        ans = answers[step]; ans = ans(prompt) if callable(ans) else ans
        return {"rc": 0, "killed": None, "wall_s": 0.1, "prompt_bytes": 1, "out_bytes": 1, "text": json.dumps(ans, ensure_ascii=False)}
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
                                 "language": "en", "genre": "memoir", "categories": ["china_modern"], "level": "acquired", "rights": "public_domain"}]})
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

    def test_model_never_supplies_the_original(self):
        ans = {"select": {"skip": "没有完整段落"}}
        self.assertEqual(excerpt.run("BK-X", (0, 20), "ex-2", "china_modern", call=fake(ans), out_root=self.out)["outcome"], "skipped")
        self.assertIn("不要输出原文文字", (Path(__file__).resolve().parents[1] / "src/history_in_practice/prompts/excerpt_select.md").read_text())


if __name__ == "__main__":
    unittest.main()

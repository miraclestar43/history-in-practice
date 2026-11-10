"""A human translation printed inside an annotated edition (【原文】/【注释】/【译文】) read as the column's text, and the
local inbox for books the owner downloads by hand. LABELLED SYNTHETIC FIXTURES built here; the real-file run (the
中国文史出版社《史记（全新足本·精注全译）》) is recorded in docs/VERNACULAR_SOURCES_20261109.md."""
import io, json, sys, tempfile, unittest, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import books, render
from test_books import epub

VIEW = {"img_mark": "□", "sections": {"keep": ["【译文】"], "drop": ["【原文】", "【注释】"]}}

# Two chapters as the edition lays them out: editor's preface, original + notes blocks, the translation at the end;
# the first chapter spills into a second file that opens on a label; a contents page; a rare character as a picture.
ANNOTATED = [
    "<h1>目录</h1><p>甲本纪第一</p><p>乙列传第二</p>",
    "<h1>甲本纪第一</h1><p>编者题解：这一篇讲甲。</p><h3>【原文】</h3><p>甲者，古之人也<sup><a href='#a1'>[1]</a></sup>。</p>"
    "<h3>【注释】</h3><p class='note'>[1]古：从前。</p><h3>【原文】</h3><p>甲乃行。</p>",
    "<h3>【注释】</h3><p class='note'>[1]行：走。</p><h3>【译文】</h3><div class='yw'><p>甲是从前的人。</p>"
    "<p>甲于是出发，骑着<img src='../images/1.gif' alt='alt'/>马。</p></div>",
    "<h1>乙列传第二</h1><p>编者题解：乙。</p><h3>【原文】</h3><p>乙曰：善。</p><h3>【注释】</h3><p>无。</p>"
    "<h3>【译文】</h3><div class='yw'><p>乙说：“好。”</p></div>",
]


def load(chapters, e):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "b.epub"; p.write_bytes(epub(chapters))
        return books.load(p, e)


class TranslationView(unittest.TestCase):
    def test_only_the_translation_and_chapter_titles_are_kept(self):
        b = load(ANNOTATED, {"view": VIEW})
        texts = [p["text"] for p in b["paragraphs"]]
        self.assertEqual(texts, ["甲本纪第一", "甲是从前的人。", "甲于是出发，骑着□马。", "乙列传第二", "乙说：“好。”"])
        self.assertEqual([c["title"] for c in b["chapters"]], ["甲本纪第一", "乙列传第二"])        # contents page and the split file are not chapters
        self.assertEqual([c["first_para"] for c in b["chapters"]], [0, 3])
        self.assertEqual([p["chapter"] for p in b["paragraphs"]], [0, 0, 0, 1, 1])
        self.assertFalse(any(x in t for t in texts for x in ("[1]", "编者题解", "甲者", "【")))
        self.assertEqual(b["img_mark"], "□")

    def test_without_a_view_the_book_reads_as_before(self):
        plain = load(ANNOTATED, None)
        self.assertIn("甲者，古之人也[1]。", [p["text"] for p in plain["paragraphs"]])
        self.assertIn("甲于是出发，骑着马。", [p["text"] for p in plain["paragraphs"]])      # no picture mark unless asked for
        self.assertNotIn("sections", plain)


class Inbox(unittest.TestCase):
    def test_scan_unpacks_archives_dedupes_and_import_keeps_the_original(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); inbox, work, store = d / "Downloads", d / "inbox", d / "files"; inbox.mkdir()
            book = epub(["<h1>One</h1><p>Text.</p>"])
            (inbox / "a.epub").write_bytes(book)
            z = io.BytesIO(); zf = zipfile.ZipFile(z, "w"); zf.writestr("set/Fixture-2.epub", epub(["<p>Other.</p>", "<p>x</p>"])); zf.writestr("readme.url", "x"); zf.close()
            (inbox / "pack.zip").write_bytes(z.getvalue()); (inbox / "notes.docx").write_bytes(b"x")
            man = d / "manifest.json"
            rows = books.scan_inbox(inbox, work, man, [{"book_id": "BK-F", "title": "Fixture"}])
            self.assertEqual(sorted(r["file"] for r in rows), ["Fixture-2.epub", "a.epub"])
            self.assertTrue(all(r["status"] == "possible_duplicate" and r["same_title_in_library"] == ["BK-F"] for r in rows))
            self.assertEqual(next(r for r in rows if r["file"] == "Fixture-2.epub")["from_archive"], "pack.zip")
            self.assertTrue((inbox / "pack.zip").exists())                                     # the download is kept
            rec = books.import_local(inbox / "a.epub", store, man, {"book_id": "BK-F", "title": "Fixture"})
            self.assertEqual((store / "BK-F.epub").read_bytes(), book); self.assertEqual(rec["original_name"], "a.epub")
            self.assertTrue((inbox / "a.epub").exists())
            again = books.scan_inbox(inbox, work, man, [])
            self.assertEqual(next(r for r in again if r["file"] == "a.epub")["status"], "acquired")
            with self.assertRaises(books.BookError):                                             # same bytes under another id
                books.import_local(inbox / "a.epub", store, man, {"book_id": "BK-G", "title": "x"})

    def test_archive_with_unsafe_names_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); inbox = d / "in"; inbox.mkdir()
            z = io.BytesIO(); zf = zipfile.ZipFile(z, "w"); zf.writestr("../evil.epub", b"x"); zf.close()
            (inbox / "bad.zip").write_bytes(z.getvalue())
            rows = books.scan_inbox(inbox, d / "work", d / "m.json", [])
            self.assertEqual(rows[0]["status"], "archive_error")
            self.assertFalse((d / "evil.epub").exists())


class Credit(unittest.TestCase):
    def test_byline_names_the_human_translator(self):
        obj = {"work": {"author": "Sima Qian", "author_zh": "司马迁", "title": "史记", "role": {"zh": "原著", "en": "original author"},
                        "chapter_zh": "袁盎晁错列传第四十一", "translator": "石磊 主编（各篇译者书中未署名）",
                        "translator_en": "modern Chinese translation, ed. Shi Lei", "original_language": "zh"}}
        self.assertIn("司马迁 原著", render.byline(obj, "zh")); self.assertIn("白话译文：石磊 主编（各篇译者书中未署名）", render.byline(obj, "zh"))
        self.assertIn("ed. Shi Lei", render.byline(obj, "en")); self.assertIn("AI translation", render.byline(obj, "en"))


if __name__ == "__main__":
    unittest.main()


class PrivateAndPaired(unittest.TestCase):
    def test_private_entries_never_reach_the_public_library_file(self):
        import os
        from unittest import mock
        from history_in_practice import library
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); pub = d / "library.json"; pub.write_text(json.dumps({"schema": "library/1", "books": [{"book_id": "BK-PUB", "title": "p", "level": "usable"}]}))
            with mock.patch.object(library, "LIB", pub), mock.patch.dict(os.environ, {"HIP_DATA_DIR": str(d / "data")}):
                lib = library.load()
                lib["books"].append({"book_id": "BK-MINE", "title": "mine", "level": "usable", "private": True})
                library.save(lib)
                self.assertNotIn("BK-MINE", pub.read_text())
                self.assertIn("BK-MINE", library.private_path().read_text())
                self.assertTrue(library.get(library.load(), "BK-MINE")["private"])
                self.assertEqual(library.entries(), [])                       # private books never enter the supply

    def test_pair_check_reads_spelled_numbers_and_flags_a_shifted_pair(self):
        from history_in_practice import excerpt
        good = [{"p": 1, "tr_p": 7, "en": "They sold three thousand pounds of butter and raised sixty pounds in 1620.", "zh": "他们卖掉了3000磅黄油，筹集了60英镑[25]。1620年。"},
                {"p": 2, "tr_p": 8, "en": "John Carver (the governor) wrote to Thomas Weston at length about the terms.", "zh": "约翰·卡弗（John Carver）给托马斯·韦斯顿写了长信。"}]
        self.assertEqual(excerpt.pair_check(good, "en", "zh")["doubtful"], [])
        shifted = [dict(good[0], zh=good[1]["zh"]), dict(good[1], zh=good[0]["zh"])]
        self.assertTrue(excerpt.pair_check(shifted, "en", "zh")["doubtful"])

    def test_review_fix_never_rewrites_a_human_translation(self):
        from history_in_practice import excerpt
        obj = {"work": {"original_language": "en"}, "translation": {"human": True}, "passage": [{"p": 3, "en": "x", "zh": "原译"}], "title": {}, "notes": []}
        self.assertFalse(excerpt.apply_fix(obj, {"where": "tr.P3", "proposed": "改写"}))
        self.assertEqual(obj["passage"][0]["zh"], "原译")
        self.assertFalse(excerpt.apply_fix(obj, {"where": "intro.zh", "proposed": "同 Q3 修改后的全文"}))

    def test_paired_page_shows_both_texts_and_hides_endnote_marks(self):
        obj = {"title": {"zh": "标题", "en": "Title"}, "dek": {"zh": "提要", "en": "dek"}, "intro": {"zh": "导读", "en": "intro"},
               "work": {"author": "A. Author", "title": "Book", "original_language": "en", "translator": "某某", "edition": "Ed."},
               "translation": {"lang": "zh", "human": True, "label": {"zh": "人工译文", "en": "published translation"}, "by": "某某 译", "paragraphs": [7, 7]},
               "passage": [{"p": 1, "en": "The _ship_ sailed.", "zh": "船起航了[24]。", "gap_before": False}], "notes": [], "selection": {"why": "值得读"}}
        h = render.paired_html(obj)
        self.assertIn("船起航了。", h); self.assertNotIn("[24]", h); self.assertIn("<i>ship</i>", h)
        self.assertIn("中文为人工译文（某某 译）", h); self.assertNotIn("AI", h); self.assertNotIn("starhub", h)

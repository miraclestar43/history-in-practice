"""Book intake pilot (books.py) on LABELLED SYNTHETIC FIXTURES built here: TXT encodings and Gutenberg boilerplate,
text-layer PDFs (bounded pdftotext, 1-based page locations, scanned -> needs_ocr), fork files verified by Git blob hash,
EPUB spine order and stable locations, untrusted-input refusals (ZIP names/bombs, DRM, entity declarations),
book text -> evidence excerpt -> book location, catalogue leads (dedupe, never evidence) and acquisition caps.
The real-file run is recorded in docs/AFK_TEST_AND_BOOKS_REPORT.md."""
import io, json, sys, tempfile, unittest, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import books, evidence


def epub(chapters, *, extra=None, mimetype=b"application/epub+zip", opf_prefix="", names=None):
    b = io.BytesIO(); z = zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED)
    if mimetype is not None:
        z.writestr("mimetype", mimetype)
    z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
               '<rootfiles><rootfile full-path="OPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    items = "".join(f'<item id="c{i}" href="{(names or {}).get(i, f"c{i}.xhtml")}" media-type="application/xhtml+xml"/>' for i in range(len(chapters)))
    spine = "".join(f'<itemref idref="c{i}"/>' for i in range(len(chapters)))
    z.writestr("OPS/content.opf", f'{opf_prefix}<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/">'
               f'<metadata><dc:title>Fixture</dc:title><dc:creator>Nobody</dc:creator><dc:language>en</dc:language></metadata>'
               f'<manifest>{items}</manifest><spine>{spine}</spine></package>')
    for i, body in enumerate(chapters):
        if not (names or {}).get(i, "").startswith(".."):
            z.writestr(f"OPS/{(names or {}).get(i, f'c{i}.xhtml')}", f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title>'
                       f'<script>alert(1)</script></head><body>{body}</body></html>')
    for n, d in (extra or {}).items():
        z.writestr(n, d)
    z.close(); return b.getvalue()


CH = ["<p>Licence and credits: this file comes from Wikisource under CC BY-SA.</p>",
      "<h1>Chapter One</h1><p>First paragraph of the story &amp; more.</p><p>Second paragraph, with a<br/>line break.</p>",
      "<h2>Chapter Two</h2><div>Text in a div.</div><ul><li>An item</li></ul>",
      "<p>About this digital edition: exported by ws-export from Wikisource.</p>"]


class Txt(unittest.TestCase):
    def test_encodings_and_gutenberg_boilerplate(self):
        raw = "Header junk\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\n\n第一章 起\n\n甲乙丙丁戊己庚辛\n壬癸。\n\n第二章 承\n\n子丑寅卯。\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\nLicence"
        for enc in ("utf-8", "gb18030", "big5"):
            b = books.parse_txt(raw.encode(enc))
            self.assertEqual(b["encoding"], enc); self.assertTrue(b["gutenberg_boilerplate_removed"])
            self.assertEqual([c["title"] for c in b["chapters"]], ["第一章 起", "第二章 承"])
            self.assertEqual(b["paragraphs"][1]["text"], "甲乙丙丁戊己庚辛壬癸。")              # hard-wrapped CJK lines joined
            self.assertNotIn("Licence", json.dumps(b["paragraphs"], ensure_ascii=False))
            for p in b["paragraphs"]:                                                       # offsets point into the normalised text
                self.assertEqual(b["norm_text"][p["loc"]["offset"]:p["loc"]["offset"] + p["loc"]["length"]].replace("\n", ""), p["text"])
        b1, b2 = books.parse_txt(raw.encode()), books.parse_txt(("﻿" + raw.replace("\n", "\r\n")).encode())
        self.assertEqual(b1["norm_sha256"], b2["norm_sha256"]); self.assertEqual([p["loc"] for p in b1["paragraphs"]], [p["loc"] for p in b2["paragraphs"]])

    def test_undecodable_is_refused(self):
        with self.assertRaises(books.BookError):
            books.decode(b"\x80\xff\x80\xff")              # invalid in UTF-8, GB18030 and Big5


class Epub(unittest.TestCase):
    def test_spine_order_locations_and_boilerplate(self):
        b = books.parse_epub(epub(CH))
        self.assertEqual([c["title"] for c in b["chapters"]], ["Chapter One", "Chapter Two"])
        self.assertEqual([s["why"] for s in b["skipped"]], ["boilerplate (licence/credits/about)"] * 2)
        texts = [p["text"] for p in b["paragraphs"]]
        self.assertEqual(texts, ["Chapter One", "First paragraph of the story & more.", "Second paragraph, with a line break.",
                                 "Chapter Two", "Text in a div.", "An item"])
        self.assertNotIn("alert", " ".join(texts))
        self.assertEqual(b["paragraphs"][2]["loc"], {"spine": 1, "href": "OPS/c1.xhtml", "para": 2})
        self.assertEqual(books.parse_epub(epub(CH))["norm_sha256"], b["norm_sha256"])

    def test_untrusted_inputs_are_refused(self):
        bad = {"traversal": epub(CH, extra={"../evil.txt": "x"}),
               "drm": epub(CH, extra={"META-INF/encryption.xml": "<encryption/>"}),
               "entity_opf": epub(CH, opf_prefix='<!DOCTYPE p [<!ENTITY x "y">]>'),
               "bomb": epub(CH, extra={"OPS/bomb.txt": "0" * 5_000_000}),
               "mimetype": epub(CH, mimetype=None),
               "outside": epub(CH[:2], names={1: "../c1.xhtml"}),
               "not_zip": b"PK\x03\x04 not really"}
        b = io.BytesIO(); z = zipfile.ZipFile(b, "w"); z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", '<?xml version="1.0"?><!DOCTYPE c [<!ENTITY lol "lol">]><container/>'); z.close()
        bad["entity_doc"] = b.getvalue()
        for name, data in bad.items():
            with self.subTest(name), self.assertRaises(books.BookError):
                books.parse_epub(data)


class ToEvidence(unittest.TestCase):
    def test_excerpt_maps_back_to_book_location(self):
        td = Path(tempfile.mkdtemp()); cache = td / "cache"
        for cjk, data, a, z in ((False, epub(CH), "Second paragraph", "line break."),
                                (True, "第一章\n\n甲乙丙丁，戊己。\n\n庚辛壬癸，子丑寅卯。\n".encode("gb18030"), "庚辛", "寅卯。")):
            b = books.parse_epub(data) if not cjk else books.parse_txt(data); b["file_sha256"] = "f"
            meta = books.to_source(b, "S-BK", cache, {"title": "t", "must_contain": [a], "verified": True}, cjk=cjk)
            self.assertEqual(meta["status"], "evidence_usable")
            pack, err = evidence.build([["E1", "S-BK", a, z, "loc"]], {"S-BK": dict(meta, ref="book:x", cjk=cjk)}, cache)
            self.assertEqual(err, [])
            loc = books.book_location(cache, "S-BK", pack["excerpts"][0]["offset"])
            want = next(p["loc"] for p in b["paragraphs"] if evidence.normalise(a, cjk) in evidence.normalise(p["text"], cjk))
            self.assertEqual(loc, want)

    def test_unverified_edition_is_never_evidence_usable(self):
        td = Path(tempfile.mkdtemp()); b = books.parse_epub(epub(CH)); b["file_sha256"] = "f"
        self.assertEqual(books.to_source(b, "S1", td, {"must_contain": ["Chapter One"]}, cjk=False)["status"], "unverified")
        self.assertEqual(books.to_source(b, "S2", td, {"must_contain": ["absent"], "verified": True}, cjk=False)["status"], "extractable")


class Catalogue(unittest.TestCase):
    def test_dedupe_merge_tags_and_provenance_never_evidence(self):
        db = books.catalogue_db(Path(tempfile.mkdtemp()) / "d.sqlite")
        rows = [{"title": "李鴻章傳", "author": "梁啟超", "category": "传记", "language": "ZH", "formats": ["epub"], "link": "https://host.example/f/1"},
                {"title": "李鸿章传（精装本）", "author": "梁启超", "category": "近代史", "language": "ZH", "formats": ["mobi"], "link": "https://host.example/f/2"},
                {"title": "李鸿章传", "author": "张三", "category": "传记"}, {"bad": 1}]
        rep = books.import_catalogue(db, rows, "fixture")
        self.assertEqual((rep["rows"], rep["new_leads"], rep["merged_duplicates"]), (3, 2, 1))
        tags, prov, ed, status = db.execute("SELECT tags, provenance, edition_notes, status FROM lead WHERE author='梁啟超'").fetchone()
        self.assertEqual(json.loads(tags), ["传记", "近代史"]); self.assertEqual(json.loads(ed), ["精装本"]); self.assertEqual(status, "lead")
        self.assertTrue(all("not followed" in p["link_status"] for p in json.loads(prov)))


class Acquire(unittest.TestCase):
    def fake(self, body, ctype="application/epub+zip"):
        class R(io.BytesIO):
            headers = {"Content-Type": ctype}
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return lambda req, timeout=0: R(body)

    def test_caps_and_wrong_content(self):
        td = Path(tempfile.mkdtemp()); man = td / "m.json"; meta = lambda i: {"book_id": f"B{i}", "format": "epub"}
        old = dict(books.LIMITS); books.LIMITS.update(max_file_bytes=100, max_files=2)
        try:
            with self.assertRaises(books.BookError): books.acquire("http://example.invalid/b", td, man, meta(0), opener=self.fake(b"x" * 101))
            with self.assertRaises(books.BookError): books.acquire("http://example.invalid/b", td, man, meta(0), opener=self.fake(b"<html>login</html>", "text/html"))
            for i in range(2):
                books.acquire("http://example.invalid/b", td, man, meta(i), opener=self.fake(b"x" * 10))
            with self.assertRaises(books.BookError): books.acquire("http://example.invalid/b", td, man, meta(9), opener=self.fake(b"x"))
            self.assertEqual(len(json.loads(man.read_text())["files"]), 2)
        finally:
            books.LIMITS.clear(); books.LIMITS.update(old)


def pdf(pages):
    """A minimal LABELLED SYNTHETIC PDF (Helvetica text lines per page; an empty list = a page with no text layer)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        body = "BT /F1 11 Tf 72 740 Td " + " ".join(f"({l}) Tj 0 -14 Td" for l in lines) + " ET" if lines else "0 0 m 10 10 l S"
        objs.append(f"<< /Length {len(body)} >>\nstream\n{body}\nendstream"); c = len(objs)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {c} 0 R /Resources << /Font << /F1 3 0 R >> >> >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()


class Pdf(unittest.TestCase):
    def test_text_layer_pages_paragraphs_and_locations(self):
        pages = [["Chapter One", "", "The first paragraph starts here and goes on across", "a hard wrap to its end.", "", "1"],
                 ["Second page text that is long enough to count as a real text page.", "", "2"]]
        b = books.parse_pdf(pdf(pages))
        self.assertEqual(b["pdf_text_status"], "text"); self.assertEqual(b["quality"]["pages"], 2)
        texts = [p["text"] for p in b["paragraphs"]]
        self.assertIn("The first paragraph starts here and goes on across a hard wrap to its end.", texts)
        self.assertNotIn("1", texts); self.assertNotIn("2", texts)                                    # page numbers dropped
        second = next(p for p in b["paragraphs"] if p["text"].startswith("Second page"))
        self.assertEqual(second["loc"], {"page": 2, "para": 0})                                         # 1-based file page index
        self.assertIn("PDF page 2 (1-based", books.locator(b, second["loc"]))
        self.assertEqual(books.parse_pdf(pdf(pages))["norm_sha256"], b["norm_sha256"])

    def test_scanned_pdf_is_flagged_and_never_evidence(self):
        b = books.parse_pdf(pdf([[], [], ["only one page with a short line of text in it here"]]))
        self.assertEqual(b["pdf_text_status"], "needs_ocr"); self.assertEqual(b["paragraphs"], [])
        b["file_sha256"] = "f"
        meta = books.to_source(b, "S-SCAN", Path(tempfile.mkdtemp()), {"must_contain": [], "verified": True}, cjk=False)
        self.assertEqual(meta["status"], "needs_ocr")
        with self.assertRaises(books.BookError):
            books.parse_pdf(b"%PDF-1.4 not really a pdf")

    def test_cjk_rejoin_running_headers_and_paragraph_ends(self):
        head = "胡适口述自传"
        pages = [[head, "第八章 从文学革命到文艺复兴", "我那首诗在我的朋友们之间引起了一场是非。梅、任", "两君都参加了对我的辩论。", "所以我们辩论不休，愈辩则牵涉愈多，内容也愈复杂", "愈精湛。", "88"]] + \
                [[head, s, str(88 + i)] for i, s in enumerate(["甲乙丙丁戊己庚辛壬癸。", "子丑寅卯辰巳午未申酉。", "春夏秋冬东南西北。",
                                                              "金木水火土日月星辰。", "宫商角徵羽山川草木。"], 1)]
        paras, chapters, dropped = books.pdf_paragraphs(["\n".join(p) for p in pages])
        texts = [p["text"] for p in paras]
        self.assertEqual(texts[:3], ["第八章 从文学革命到文艺复兴", "我那首诗在我的朋友们之间引起了一场是非。梅、任两君都参加了对我的辩论。",
                                     "所以我们辩论不休，愈辩则牵涉愈多，内容也愈复杂愈精湛。"])         # heading apart; CJK joined without spaces
        self.assertNotIn(head, texts); self.assertEqual(dropped["running_lines"], 6); self.assertEqual(dropped["page_numbers"], 6)
        self.assertEqual(chapters[0]["title"], "第八章 从文学革命到文艺复兴"); self.assertEqual(paras[0]["loc"]["page"], 1)


class Fork(Acquire):
    def test_git_blob_must_match_the_pinned_tree(self):
        body = b"%PDF-1.4 fake book bytes"; tree = [{"path": "12-史/书.pdf", "type": "blob", "sha": books.git_blob_sha(body), "size": len(body)}]
        loc = books.fork_file("me/fork", "a" * 40, tree, "12-史/书.pdf")
        self.assertEqual(loc["url"], "https://raw.githubusercontent.com/me/fork/" + "a" * 40 + "/12-%E5%8F%B2/%E4%B9%A6.pdf")
        td = Path(tempfile.mkdtemp()); man = td / "m.json"; meta = {"book_id": "B1", "format": "pdf", "git_blob": loc["git_blob"]}
        lfs = b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n"
        with self.assertRaisesRegex(books.BookError, "not Git blob"):
            books.acquire(loc["url"], td, man, meta, opener=self.fake(lfs, "application/octet-stream"))
        rec = books.acquire(loc["url"], td, man, meta, opener=self.fake(body, "application/octet-stream"))
        self.assertEqual(rec["git_blob"], books.git_blob_sha(body))
        with self.assertRaises(books.BookError):
            books.fork_file("me/fork", "a" * 40, tree, "missing.pdf")


if __name__ == "__main__":
    unittest.main()

"""The public repository is not a copy of any in-copyright book (owner 2026-11-01): tracked files keep articles, records
and short quotations; book-sourced evidence packs stay on the Pi. Runs where the book caches exist (the Pi)."""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "validation")); sys.path.insert(0, str(ROOT / "src"))
import public_text_audit
from history_in_practice import render


class PublicRepo(unittest.TestCase):
    def test_no_tracked_file_holds_long_book_text(self):
        if not public_text_audit.copyrighted_caches():
            self.skipTest("no local book caches (not the Pi)")
        r = public_text_audit.audit(1500, 400)
        self.assertEqual(r["over"], [], r["files"][:5])

    def test_readers_are_never_linked_to_a_book_file(self):
        self.assertFalse(render.web_url("https://raw.githubusercontent.com/a/b/0123/13-x/%E8%83%A1.pdf"))
        self.assertFalse(render.web_url("https://github.com/a/b/blob/main/x.epub"))
        self.assertTrue(render.web_url("https://zh.wikisource.org/wiki/x"))
        tpl = (ROOT / "src/history_in_practice/templates/history_index.html").read_text()
        self.assertIn("!BOOK_FILE.test(x)", tpl)


if __name__ == "__main__":
    unittest.main()

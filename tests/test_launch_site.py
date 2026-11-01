"""Launch 2026-11-01: the production column never shows TEST material. The production export writes an index without
`mode` (no TEST banner; samples/tests/notices filtered by the page); only the TEST preview index says mode=test."""
import json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import render, site_export

ROOT = Path(__file__).resolve().parents[1]


class LaunchSite(unittest.TestCase):
    def test_production_index_has_no_test_mode_and_preview_index_does(self):
        o = json.loads((ROOT / "samples/D/article.json").read_text()); o.update(edition_date="2026-11-02", status="published")
        render.finalize(o)
        with tempfile.TemporaryDirectory() as td:
            site_export.export([o], Path(td))
            idx = json.loads((Path(td) / "data/history/index.json").read_text())
            self.assertNotIn("mode", idx); self.assertEqual([i["edition_id"] for i in idx["items"]], [o["edition_id"]])
            s = dict(o, status="reader_sample", preview_date="2026-11-02", edition_id="x-sample"); s.pop("edition_date"); render.finalize(s)
            site_export.preview(Path(td), [s])
            self.assertEqual(json.loads((Path(td) / "data/history/index.json").read_text())["mode"], "test")
        tpl = (ROOT / "src/history_in_practice/templates/history_index.html").read_text()
        self.assertIn('const isTest = index.mode === "test"', tpl)
        self.assertIn("index.items.filter(i => !i.sample && !i.test && !i.notice)", tpl)


if __name__ == "__main__":
    unittest.main()

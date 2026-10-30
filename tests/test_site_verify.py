import copy, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import render, site_export

ROOT = Path(__file__).resolve().parents[1]


def frozen():
    o = json.loads((ROOT / "samples/D/article.json").read_text()); render.finalize(o); return o


def site_with(obj, *, index_ct="application/json", edition_ct="application/json", index_body=None, edition_obj=None):
    path = "data/history/2026/11/05-sample-D.json"
    idx = index_body if index_body is not None else json.dumps({"items": [{"edition_id": obj["edition_id"], "revision": obj["revision"], "path": path}]}).encode()
    ed = json.dumps(edition_obj if edition_obj is not None else obj).encode()
    home = b"<!DOCTYPE html><title>StarHub | Command Center</title>"
    def fetch(url, timeout=20):
        if url.endswith("/data/history/index.json"):
            return 200, index_ct, (home if index_ct.startswith("text/html") else idx)
        if url.endswith(path):
            return 200, edition_ct, (home if edition_ct.startswith("text/html") else ed)
        return 200, "text/html", home            # starhub: unknown paths return the homepage with 200
    return fetch


class Verify(unittest.TestCase):
    def test_good_deploy_passes(self):
        o = frozen(); ok, p = site_export.verify(o, "https://x", fetch=site_with(o)); self.assertTrue(ok, p)

    def test_site_fallback_200_homepage_is_not_success(self):
        o = frozen(); ok, p = site_export.verify(o, "https://x", fetch=site_with(o, index_ct="text/html; charset=utf-8"))
        self.assertFalse(ok); self.assertIn("fallback", p[0])

    def test_old_revision_detected(self):
        o = frozen(); old = copy.deepcopy(o); old["revision"] = o["revision"] - 1 if o["revision"] > 1 else 0
        ok, p = site_export.verify(o, "https://x", fetch=site_with(o, edition_obj=old)); self.assertFalse(ok)
        self.assertTrue(any("revision" in x for x in p))

    def test_same_id_and_title_but_changed_body_detected(self):
        o = frozen(); live = copy.deepcopy(o); live["sections"][2]["paras"][0]["zh"] += "（被改动）"
        ok, p = site_export.verify(o, "https://x", fetch=site_with(o, edition_obj=live)); self.assertFalse(ok)
        self.assertTrue(any("hash" in x for x in p))

    def test_missing_english_detected(self):
        o = frozen(); live = copy.deepcopy(o)
        for s in live["sections"]:
            for para in s["paras"]: para["en"] = ""
        ok, p = site_export.verify(o, "https://x", fetch=site_with(o, edition_obj=live)); self.assertFalse(ok)
        self.assertTrue(any("language en" in x for x in p))


class Export(unittest.TestCase):
    def test_export_writes_only_allowed_paths_and_refuses_others(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / "articles.html").write_text("private vault"); (root / "data/articles").mkdir(parents=True)
            written = site_export.export([frozen()], root)
            self.assertTrue(written and all(w.startswith(("history/", "data/history/")) for w in written))
            self.assertEqual((root / "articles.html").read_text(), "private vault")
            with self.assertRaises(site_export.ExportError):
                site_export._safe_dest(root, "data/articles/index.json")
            with self.assertRaises(site_export.ExportError):
                site_export._safe_dest(root, "history/../articles.html")


if __name__ == "__main__":
    unittest.main()

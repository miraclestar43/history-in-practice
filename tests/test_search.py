"""Reader search on /history/ (owner 2026-11-01): a static index rebuilt with every publication, from published
editions only (never TEST, samples, unscheduled inventory, evidence or review records); one entry per story with both
languages; the page searches it locally. Also: the 10-15 minute length rule is what the writing agents load."""
import json, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from history_in_practice import render, site_export, pipeline


def obj(eid, date, status="published", **kw):
    o = json.loads((ROOT / "samples/D/article.json").read_text())
    o.update(edition_id=eid, status=status, **kw)
    if date:
        o["edition_date"] = date
    else:
        o.pop("edition_date", None)
    o["episode"] = {"persons": ["华盛顿"], "year_from": 1783, "year_to": 1783}
    render.finalize(o); return o


class Search(unittest.TestCase):
    def test_index_has_published_issues_only_and_follows_each_publication(self):
        pub = obj("ed-pub", "2026-11-01"); test = obj("ed-test", "2026-11-02", status="test"); inv = obj("ed-inv", "unscheduled")
        sample = dict(obj("ed-sample", None), status="reader_sample", preview_date="2026-11-02")
        with tempfile.TemporaryDirectory() as td:
            site_export.export([pub, test, inv, sample], Path(td))
            meta = json.loads((Path(td) / "data/history/search.json").read_text())
            text = json.loads((Path(td) / "data/history/search_text.json").read_text())
            self.assertEqual([i["id"] for i in meta["items"]], ["ed-pub"]); self.assertEqual([i["id"] for i in text["items"]], ["ed-pub"])
            it = meta["items"][0]
            self.assertEqual(set(it["title"]), {"zh", "en"}); self.assertIn("华盛顿", it["people"])     # both languages, one entry
            self.assertTrue(it["dek"]["zh"] and it["tags"]); self.assertTrue(text["items"][0]["zh"] and text["items"][0]["en"])
            raw = (Path(td) / "data/history/search.json").read_text() + (Path(td) / "data/history/search_text.json").read_text()
            self.assertEqual(set(it), {"id", "date", "category", "title", "dek", "people", "tags", "books", "minutes", "path"})   # no evidence,
            self.assertEqual(set(text["items"][0]), {"id", "zh", "en"}); self.assertNotIn("excerpts", raw)                  # records or ids of sources
            nxt = obj("ed-next", "2026-11-02")                                 # the next issue is published: it joins the index
            site_export.export([pub, nxt], Path(td))
            self.assertEqual([i["id"] for i in json.loads((Path(td) / "data/history/search.json").read_text())["items"]], ["ed-next", "ed-pub"])

    def test_page_searches_locally(self):
        tpl = (ROOT / "src/history_in_practice/templates/history_index.html").read_text()
        for x in ('type:"search"', "search.json", "search_text.json", "没有找到", 'searchParams.set("q"', "clr.onclick"):
            self.assertIn(x, tpl)


class LengthRule(unittest.TestCase):
    def test_ten_to_fifteen_minutes_each_language_and_no_old_target(self):
        every = {p.stem: pipeline.load_prompt(p.stem) for p in pipeline.PROMPTS.glob("*.md")}
        for name, t in every.items():
            for old in ("约十分钟", "2,900–3,400", "1,900–2,200", "about ten minutes", "中文约十分钟、英文约十分钟"):
                self.assertNotIn(old, t, name)
        for name in ("style_zh", "translate_en_long", "final_audit", "final_verify", "final_revise", "review_zh"):
            self.assertIn("10–15", every[name], name)
        self.assertIn("不是退稿或必须修改的理由", every["final_audit"])


if __name__ == "__main__":
    unittest.main()

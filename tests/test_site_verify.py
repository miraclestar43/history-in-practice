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


class Preview(unittest.TestCase):
    """TEST preview: reader samples and dated notices are added without touching what is already published."""
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()); sent = frozen(); sent.update(edition_id="test-x", status="test", edition_date="2026-10-30")
        render.finalize(sent); site_export.export([sent], self.root); self.sent = sent
        self.sent_file = self.root / "data/history/2026/10/30-test-x.json"; self.sent_bytes = self.sent_file.read_bytes()

    def sample(self):
        o = frozen(); o.update(edition_id="cand-s", status="reader_sample", preview_date="2026-10-31"); o.pop("edition_date", None); return render.finalize(o)

    def test_sample_and_notice_keep_the_sent_item_and_its_bytes(self):
        n = {"kind": "under_revision", "at": "2026-10-31", "revision": self.sent["revision"], "zh": "待修订。", "en": "Under revision."}
        site_export.preview(self.root, [self.sample()], {"test-x": n})
        idx = json.loads((self.root / "data/history/index.json").read_text())
        by = {x["edition_id"]: x for x in idx["items"]}
        self.assertEqual(set(by), {"test-x", "cand-s"}); self.assertTrue(by["cand-s"]["sample"])
        self.assertEqual(by["cand-s"]["path"], "data/history/samples/cand-s.json"); self.assertTrue((self.root / by["cand-s"]["path"]).exists())
        self.assertEqual(by["test-x"]["notice"]["kind"], "under_revision"); self.assertTrue(by["test-x"]["test"])
        self.assertEqual(self.sent_file.read_bytes(), self.sent_bytes)              # the sent TEST keeps its bytes and hash
        live = json.loads((self.root / by["cand-s"]["path"]).read_text()); self.assertEqual(live["content_sha256"], by["cand-s"]["content_sha256"])
        site_export.preview(self.root, [self.sample()])                              # idempotent: no duplicates, notice kept
        idx = json.loads((self.root / "data/history/index.json").read_text())
        self.assertEqual(len(idx["items"]), 2); self.assertIn("notice", [x for x in idx["items"] if x["edition_id"] == "test-x"][0])

    def test_notice_must_name_the_listed_revision_and_samples_must_be_samples(self):
        bad = {"kind": "under_revision", "at": "2026-10-31", "revision": 99, "zh": "x", "en": "y"}
        with self.assertRaises(site_export.ExportError): site_export.preview(self.root, [], {"test-x": bad})
        with self.assertRaises(site_export.ExportError): site_export.preview(self.root, [], {"nope": dict(bad, revision=1)})
        o = self.sample(); o["status"] = "checked"
        with self.assertRaises(site_export.ExportError): site_export.preview(self.root, [o])


class ReadMoreLinks(unittest.TestCase):
    """2026-10-31: a read-more item without a URL rendered as a link to /history/null. Only http(s) URLs are links."""
    def test_missing_url_is_plain_text_everywhere(self):
        o = frozen(); o["further_reading"] = [{"title": "某书第八章", "url": None, "what": {"zh": "原书", "en": "the book"},
                                               "access": {"zh": "纸书", "en": "print"}}]
        render.finalize(o)
        for out in (render.email_html(o, "https://x"), render.email_text(o, "https://x"), render.markdown(o, "zh"), render.markdown(o, "en")):
            self.assertNotIn("None", out); self.assertNotIn("null", out); self.assertIn("某书第八章", out)
        self.assertNotIn("](None)", render.markdown(o, "zh"))
        tpl = (ROOT / "src/history_in_practice/templates/history_index.html").read_text()
        self.assertIn("okUrl(m.url) ? el(\"a\"", tpl.replace("'", '"'))
        self.assertTrue(render.web_url("https://example.org/x")); self.assertFalse(render.web_url(None)); self.assertFalse(render.web_url("null"))


def fake_news(as_of="2026-11-02T07:00:00-08:00", status="ready", n=3):
    """Fictional snapshot: invented headlines and example.org links; contacts no one."""
    return {"schema": "news3min/v0-prototype", "snapshot_id": "fake", "revision": 1, "status": status, "as_of": as_of,
            "label": {"zh": "截至 07:00（洛杉矶时间）· 过去24小时要闻（虚构测试）", "en": "fake"},
            "items": [{"headline": f"虚构新闻{i}", "what": "某地发生了某事。", "why": "这是测试。", "why_kind": "interpretation",
                       "qualifiers": "测试限定。", "sources": [{"name": "Example", "url": f"https://example.org/{i}"}]} for i in range(n)]}


class NewsModule(unittest.TestCase):
    """prompts/08: an optional 3-minute news module in the reading email; stale or unsafe news is never shown as fresh."""
    NOW = "2026-11-02T07:30:00-08:00"

    def test_fresh_snapshot_adds_anchored_news_before_the_story(self):
        o = frozen(); h = render.email_html(o, "https://x", news=fake_news(), now_iso=self.NOW)
        self.assertEqual(render.news_problems(fake_news(), self.NOW), [])
        self.assertIn('href="#news"', h); self.assertIn('href="#story"', h); self.assertIn('id="news"', h); self.assertIn('id="story"', h)
        self.assertLess(h.index("虚构新闻0"), h.index('id="story"')); self.assertIn("编辑解读：这是测试。", h); self.assertIn("https://example.org/2", h)

    def test_why_line_is_labelled_by_kind_and_never_restates_the_headline(self):
        # owner feedback 2026-10-31: keep reported fact, a source's judgment and the editor's reading apart; a "why"
        # that only repeats the headline is dropped, not shown
        n = fake_news(); n["items"][0].update(why="分析机构认为需求推高了利润。", why_kind="source_judgment")
        self.assertIn("来源观点：分析机构认为需求推高了利润。", render.email_html(frozen(), "https://x", news=n, now_iso=self.NOW))
        rep = fake_news(); rep["items"][0].update(headline="刚果（金）埃博拉疫情死亡超过五千人", why="刚果（金）埃博拉疫情死亡超过五千人，值得关注。")
        self.assertTrue(any("restates" in x for x in render.news_problems(rep, self.NOW)))
        bad = fake_news(); bad["items"][0]["why_kind"] = "trend"
        self.assertTrue(any("why_kind" in x for x in render.news_problems(bad, self.NOW)))

    def test_stale_degraded_or_unsourced_news_is_replaced_by_a_short_note(self):
        o = frozen()
        stale = fake_news(as_of="2026-10-31T07:00:00-07:00"); degraded = fake_news(status="degraded"); few = fake_news(n=1)
        nolink = fake_news(); nolink["items"][0]["sources"] = [{"name": "X", "url": None}]
        for bad in (stale, degraded, few, nolink):
            self.assertTrue(render.news_problems(bad, self.NOW))
            h = render.email_html(o, "https://x", news=bad, now_iso=self.NOW)
            self.assertIn("新闻简报暂缺", h); self.assertNotIn("虚构新闻1", h); self.assertIn('id="story"', h)   # the story still goes out

    def test_without_news_the_email_is_unchanged(self):
        o = frozen(); self.assertEqual(render.email_html(o, "https://x"), render.email_html(o, "https://x", news=None))
        self.assertNotIn('id="news"', render.email_html(o, "https://x"))
        self.assertEqual(render.email_text(o, "https://x"), render.email_text(o, "https://x", news=None))
        txt = render.email_text(o, "https://x", news=fake_news(), now_iso=self.NOW); self.assertIn("1. 虚构新闻0", txt)
        self.assertLess(txt.index("虚构新闻2"), txt.index("== 今日故事 =="))
        self.assertIn("新闻简报暂缺", render.email_text(o, "https://x", news=fake_news(status="degraded"), now_iso=self.NOW))


if __name__ == "__main__":
    unittest.main()

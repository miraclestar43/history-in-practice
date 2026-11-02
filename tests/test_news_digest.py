"""The news digest at the end of the reading email (2026-11-01): consumer checks of news-intel's frozen brief, the
frozen per-edition binding, failure isolation and the end-of-email layout. Fictional snapshots and example.org
links only; contacts no one."""
import email, json, subprocess, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src")); sys.path.insert(0, str(Path(__file__).parent))
from history_in_practice import news, render  # noqa: E402
from test_publish import PublishFlow, at  # noqa: E402
from test_site_verify import frozen  # noqa: E402

BJ = timezone(timedelta(hours=8))
NOW = datetime(2026, 11, 2, 22, 8, tzinfo=BJ)       # the 22:08 Beijing send


def fake_brief(date="2026-11-02", n=3, status=None, cutoff=None, tz="Asia/Shanghai", rev=1):
    items = [{"headline": f"虚构新闻{i}", "what": "某地发生了某事。", "why": "", "why_kind": "",
              "brief_line": f"虚构速览{i}：某地发生了某事。", "sources": [{"name": "Example", "url": f"https://example.org/{i}"}]}
             for i in range(n)]
    snap = {"schema": news.SCHEMA, "snapshot_id": f"brief-zh-{date}-r{rev}", "revision": rev, "edition_date": date,
            "timezone": tz, "cutoff": cutoff or f"{date}T20:00:00+08:00", "status": status or ("ready" if n >= 3 else
            "short" if n else "empty"), "items": items}
    snap["text_sha256"] = news.text_sha256(snap)
    return snap


def archive_page(snap: dict) -> str:
    """As news-intel renders it: the page names its snapshot and text hash."""
    return (f'<html><head><meta name="news-intel-snapshot" content="{snap["snapshot_id"]}">'
            f'<meta name="news-intel-text-sha256" content="{snap["text_sha256"]}"></head><body>archive</body></html>')


def write_brief(export: Path, snap: dict, page: str | None = "default"):
    d = export / snap["edition_date"]; d.mkdir(parents=True, exist_ok=True)
    (d / f"{snap['snapshot_id']}.json").write_text(json.dumps(snap, ensure_ascii=False))
    if page is not None:
        (d / f"{snap['snapshot_id']}.archive.html").write_text(archive_page(snap) if page == "default" else page)
    (d / "current.json").write_text(json.dumps({"snapshot_id": snap["snapshot_id"], "file": f"{snap['snapshot_id']}.json"}))


class Check(unittest.TestCase):
    def test_fresh_brief_passes_and_a_real_short_day_is_allowed(self):
        for n in (1, 2, 3, 5):
            self.assertEqual(news.check(fake_brief(n=n), "2026-11-02", NOW), [], n)

    def test_every_unqualified_snapshot_is_refused(self):
        tampered = fake_brief(); tampered["items"][0]["what"] = "被改动。"
        old_schema = dict(fake_brief(), schema="news3min/v0-prototype")
        nolink = fake_brief(); nolink["items"][0]["sources"] = [{"name": "X", "url": None}]; nolink["text_sha256"] = news.text_sha256(nolink)
        cases = {
            "no snapshot": None, "empty": fake_brief(n=0), "six items": fake_brief(n=6), "tampered": tampered,
            "old schema": old_schema, "yesterday's edition": fake_brief(date="2026-11-01"),
            "future cutoff": fake_brief(cutoff="2026-11-02T23:00:00+08:00"),
            "stale": fake_brief(cutoff="2026-11-01T18:00:00+08:00"), "wrong time zone": fake_brief(tz="America/Los_Angeles"),
            "no source link": nolink,
        }
        for name, snap in cases.items():
            self.assertTrue(news.check(snap, "2026-11-02", NOW), name)


class Bind(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); t = Path(self.td.name)
        self.export, self.bindings = t / "exports", t / "bindings"
        self.ed = {"edition_id": "ed-1", "revision": 1, "edition_date": "2026-11-02"}

    def tearDown(self):
        self.td.cleanup()

    def bind(self, now=NOW, **kw):
        return news.bind(self.bindings, self.ed, self.export, "https://starhub.vip", now, **kw)

    def test_bound_once_then_frozen_even_if_news_intel_makes_a_new_revision(self):
        write_brief(self.export, fake_brief())
        first = self.bind()
        self.assertEqual(first["status"], "bound"); self.assertEqual(first["digest"]["url"], "https://starhub.vip/history/news/2026-11-02/")
        r2 = fake_brief(n=4, rev=2); write_brief(self.export, r2)
        again = self.bind(now=NOW + timedelta(minutes=30))           # the retry timer
        self.assertEqual(again["snapshot_id"], first["snapshot_id"]); self.assertEqual(again["text_sha256"], first["text_sha256"])

    def test_absent_stays_absent_and_a_preview_freezes_nothing(self):
        self.assertEqual(self.bind(persist=False)["status"], "absent")
        self.assertFalse(news.binding_path(self.bindings, "ed-1", 1).exists())
        self.assertEqual(self.bind()["status"], "absent")
        write_brief(self.export, fake_brief())                         # news arrives after the email step started
        self.assertEqual(self.bind()["status"], "absent")

    def test_errors_and_missing_pieces_never_raise_and_bind_absent(self):
        (self.export / "2026-11-02").mkdir(parents=True); (self.export / "2026-11-02" / "current.json").write_text("{not json")
        r = self.bind(); self.assertEqual(r["status"], "absent"); self.assertIn("could not be read", r["reason"])
        ed2 = dict(self.ed, edition_id="ed-2"); write_brief(self.export, fake_brief(), page=None)
        self.assertIn("archive page missing", news.bind(self.bindings, ed2, self.export, "https://x", NOW)["reason"])
        ed3 = dict(self.ed, edition_id="ed-3")
        self.assertIn("NEWS_EXPORT_DIR", news.bind(self.bindings, ed3, None, "https://x", NOW)["reason"])

    def test_digest_is_the_brief_lines_with_the_cutoff_and_the_archive_link(self):
        write_brief(self.export, fake_brief(n=2))
        d = self.bind()["digest"]
        self.assertTrue(d["text"].startswith("== 今日新闻速览（截至北京时间11月2日20:00） =="))
        self.assertIn("· 虚构速览1：某地发生了某事。", d["text"]); self.assertIn("完整新闻与来源：https://starhub.vip/history/news/2026-11-02/", d["text"])
        self.assertEqual(news.site_files(self.bind()), {"history/news/2026-11-02/index.html": archive_page(fake_brief(n=2))})

    def test_an_archive_page_of_another_version_or_any_other_html_is_refused(self):
        snap = fake_brief()
        cases = {"another revision": archive_page(fake_brief(n=4, rev=2)), "any html": "<html>whatever</html>",
                 "empty": "  "}
        for i, (name, page) in enumerate(cases.items()):
            write_brief(self.export, snap, page=page)
            r = news.bind(self.bindings, dict(self.ed, edition_id=f"ed-p{i}"), self.export, "https://x", NOW)
            self.assertEqual(r["status"], "absent", name); self.assertIn("archive page", r["reason"], name)

    def test_a_binding_that_cannot_be_saved_is_absent_and_no_later_step_adds_news(self):
        write_brief(self.export, fake_brief())
        orig = news._write
        news._write = lambda path, text: (_ for _ in ()).throw(OSError("disk full"))
        try:
            r = self.bind()
        finally:
            news._write = orig
        self.assertEqual(r["status"], "absent"); self.assertIn("could not be saved", r["reason"])
        self.assertFalse(news.binding_path(self.bindings, "ed-1", 1).exists())
        later = news.read_binding(self.bindings, self.ed)            # the email step, and every retry
        self.assertEqual(later["status"], "absent"); self.assertNotIn("digest", later)


class Layout(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); t = Path(self.td.name)
        write_brief(t / "e", fake_brief())
        self.bound = news.bind(t / "b", {"edition_id": "x", "revision": 1, "edition_date": "2026-11-02"}, t / "e", "https://x", NOW)

    def tearDown(self):
        self.td.cleanup()

    def test_story_first_digest_last_and_absent_news_changes_nothing(self):
        o = frozen()
        h = render.email_html(o, "https://x", news=self.bound)
        self.assertLess(h.index(o["title"]["en"]), h.index("今日新闻速览")); self.assertLess(h.index("今日新闻速览"), h.rindex(render.LBL["zh"]["feedback"]))  # before the footer
        self.assertNotIn("某地发生了某事。</p>", h.split("今日新闻速览")[0])  # no news before the story
        txt = render.email_text(o, "https://x", news=self.bound)
        self.assertGreater(txt.index("今日新闻速览"), txt.index("Read in English"))
        absent = {"status": "absent", "reason": "stale"}
        self.assertEqual(render.email_html(o, "https://x", news=absent), render.email_html(o, "https://x"))
        self.assertEqual(render.email_text(o, "https://x", news=absent), render.email_text(o, "https://x"))


class PublishWithNews(unittest.TestCase):
    """The real publish flow (test_publish.PublishFlow's fixtures, borrowed without its tests): the binding is made
    at the site step, the archive page lands on the site in the same commit, the email carries the same digest; a
    broken snapshot never holds the story back."""
    setUp, tearDown, add, served, rt, run_day, mail_rt = (PublishFlow.setUp, PublishFlow.tearDown, PublishFlow.add,
                                                         PublishFlow.served, PublishFlow.rt, PublishFlow.run_day,
                                                         PublishFlow.mail_rt)

    def html_of(self, raw):
        m = email.message_from_bytes(raw[1])  # smtp_fixture stores (rcpt, bytes)
        return next(p.get_payload(decode=True).decode() for p in m.walk() if p.get_content_type() == "text/html")

    def test_news_is_bound_at_the_site_step_published_with_the_story_and_sent_at_the_end(self):
        export = self.t / "news"; write_brief(export, fake_brief(cutoff="2026-11-02T20:00:00+08:00"))
        rt = self.rt(NEWS_EXPORT_DIR=str(export))
        r = self.publish.publish_today(self.db, rt, date="2026-11-02", fetch=self.served(), clock=at("2026-11-02", "07:30"),
                                       sleep=self.slept.append)
        self.assertEqual(r["news"]["status"], "bound")
        files = subprocess.run(["git", "-C", str(self.site), "show", "--name-only", "--format=", "HEAD"], capture_output=True, text=True).stdout.split()
        self.assertIn("history/news/2026-11-02/index.html", files)
        write_brief(export, fake_brief(n=5, rev=2))                     # a later revision must not change this edition
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            r2 = self.run_day(self.mail_rt(srv, NEWS_EXPORT_DIR=str(export)), "2026-11-02", "07:40")
            self.assertEqual(r2["outcome"], "complete"); self.assertEqual(r2["news"]["snapshot_id"], "brief-zh-2026-11-02-r1")
            h = self.html_of(srv.messages[0])
            self.assertIn("今日新闻速览", h); self.assertIn("虚构速览2", h); self.assertNotIn("虚构速览3", h)
            self.assertLess(h.index("Read in English"), h.index("今日新闻速览"))
        finally:
            srv.shutdown(); srv.server_close()

    def test_a_damaged_snapshot_never_holds_the_story_back(self):
        export = self.t / "news"; bad = fake_brief(); bad["items"][0]["what"] = "被改动。"; write_brief(export, bad)
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            r = self.run_day(self.mail_rt(srv, NEWS_EXPORT_DIR=str(export)), "2026-11-02")
            self.assertEqual(r["outcome"], "complete"); self.assertEqual(r["news"]["status"], "absent")
            self.assertIn("text_sha256", r["news"]["reason"]); self.assertNotIn("今日新闻速览", self.html_of(srv.messages[0]))
            files = subprocess.run(["git", "-C", str(self.site), "show", "--name-only", "--format=", "HEAD"], capture_output=True, text=True).stdout.split()
            self.assertFalse(any(f.startswith("history/news/") for f in files))
        finally:
            srv.shutdown(); srv.server_close()




class PublishRetries(unittest.TestCase):
    """Real publish flow (PublishFlow fixtures): a retry after some recipients were accepted carries the same news, never
    resends to them, and an email step never binds news the site step did not."""
    setUp, tearDown, add, served, rt, run_day, mail_rt = (PublishFlow.setUp, PublishFlow.tearDown, PublishFlow.add,
                                                         PublishFlow.served, PublishFlow.rt, PublishFlow.run_day,
                                                         PublishFlow.mail_rt)

    def html_of(self, raw):
        m = email.message_from_bytes(raw[1])
        return next(p.get_payload(decode=True).decode() for p in m.walk() if p.get_content_type() == "text/html")

    def test_partial_send_then_retry_keeps_the_same_news_and_the_accepted_recipient(self):
        export = self.t / "news"; write_brief(export, fake_brief())
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            srv.refuse_rcpt = {"r2@example.com"}
            r1 = self.run_day(self.mail_rt(srv, NEWS_EXPORT_DIR=str(export)), "2026-11-02")
            self.assertEqual(r1["outcome"], "partial"); self.assertEqual(r1["news"]["snapshot_id"], "brief-zh-2026-11-02-r1")
            write_brief(export, fake_brief(n=5, rev=2))                 # news-intel makes r2 meanwhile
            srv.refuse_rcpt = set(); n = len(srv.messages)
            r2 = self.run_day(self.mail_rt(srv, NEWS_EXPORT_DIR=str(export)), "2026-11-02", "08:30")
            self.assertEqual(r2["outcome"], "complete"); self.assertEqual(len(srv.messages), n + 1)   # only r2@ resent
            self.assertEqual(r2["news"]["snapshot_id"], "brief-zh-2026-11-02-r1")
            self.assertEqual(srv.messages[-1][0], "r2@example.com")
            h = self.html_of(srv.messages[-1]); self.assertIn("虚构速览2", h); self.assertNotIn("虚构速览4", h)
        finally:
            srv.shutdown(); srv.server_close()

    def test_news_that_could_not_be_bound_at_the_site_step_never_appears_later(self):
        export = self.t / "news"; write_brief(export, fake_brief())
        orig = news._write
        news._write = lambda path, text: (_ for _ in ()).throw(OSError("read-only"))
        try:                                                        # site step: binding cannot be saved
            r = self.run_day(self.rt(NEWS_EXPORT_DIR=str(export)), "2026-11-02")
        finally:
            news._write = orig
        self.assertEqual(r["news"]["status"], "absent")
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:                                                        # email step: the snapshot is fine now, still no news
            r2 = self.run_day(self.mail_rt(srv, NEWS_EXPORT_DIR=str(export)), "2026-11-02", "07:40")
            self.assertEqual(r2["outcome"], "complete"); self.assertEqual(r2["news"]["status"], "absent")
            self.assertTrue(all("今日新闻速览" not in self.html_of(m) for m in srv.messages))
        finally:
            srv.shutdown(); srv.server_close()


del PublishFlow  # its own tests run in test_publish.py, not twice

if __name__ == "__main__":
    unittest.main()

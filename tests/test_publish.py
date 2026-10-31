import json, os, shutil, subprocess, sys, tempfile, unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src")); sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).resolve().parents[1]
LA = ZoneInfo("America/Los_Angeles")


def at(date, hm="07:30"):
    h, m = map(int, hm.split(":"))
    return lambda: datetime.fromisoformat(date).replace(hour=h, minute=m, tzinfo=LA)


class PublishFlow(unittest.TestCase):
    """Daily flow with local fixtures: temp content dir, temp website git repo with a bare remote,
    live check served from the working copy, local SMTPS, injected clock and sleep."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); t = self.t = Path(self.td.name)
        os.environ["HIP_DATA_DIR"] = str(t / "data"); os.environ["HIP_CONTENT_DIR"] = str(t / "content")
        from history_in_practice import state, publish, config, render
        self.state, self.publish, self.config, self.render = state, publish, config, render
        self.db = state.connect(t / "data" / "s.sqlite")
        self.remote = t / "remote.git"; subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        self.site = t / "site"; self.site.mkdir()
        (self.site / "articles.html").write_text("private vault"); (self.site / "index.html").write_text("home")
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.site)], check=True)
        for k, v in (("user.email", "t@example.invalid"), ("user.name", "t")):
            subprocess.run(["git", "-C", str(self.site), "config", k, v], check=True)
        subprocess.run(["git", "-C", str(self.site), "add", "-A"], check=True); subprocess.run(["git", "-C", str(self.site), "commit", "-qm", "init"], check=True)
        subprocess.run(["git", "-C", str(self.site), "remote", "add", "origin", str(self.remote)], check=True)
        subprocess.run(["git", "-C", str(self.site), "push", "-q", "-u", "origin", "main"], check=True)
        self.add("sample-A", "A", "china_ancient")
        self.slept = []
        from history_in_practice import final_edit           # these flow fixtures have no final-editor records: eligibility is a switch
        self.ineligible = set(); old = (final_edit.current_eligibility, final_edit.send_problems)
        final_edit.current_eligibility = lambda db, eid, *a, **k: (["fixture: not eligible"] if eid in self.ineligible else [], None)
        final_edit.send_problems = lambda db, o, *a, **k: ["fixture: not eligible"] if o["edition_id"] in self.ineligible else []
        self.addCleanup(lambda: (setattr(final_edit, "current_eligibility", old[0]), setattr(final_edit, "send_problems", old[1])))

    def add(self, eid, s, cat, approval="editor-record", origin="pipeline"):
        art = self.t / "drafts" / f"{eid}.json"; art.parent.mkdir(parents=True, exist_ok=True)
        o = json.loads((ROOT / f"samples/{s}/article.json").read_text()); self.render.finalize(o); art.write_text(json.dumps(o))
        self.state.transition(self.db, eid, "prepared", category=cat, path=str(art))
        self.state.transition(self.db, eid, "checked", content_sha256=o["content_sha256"], approval=approval, origin=origin)
        return o

    def tearDown(self):
        self.td.cleanup(); os.environ.pop("HIP_DATA_DIR"); os.environ.pop("HIP_CONTENT_DIR")

    def served(self, stale_first=0):
        site, n = self.site, {"i": 0}
        def fetch(url, timeout=20):
            rel = url.split("://", 1)[1].split("/", 1)[1]
            if rel.endswith("index.json"):
                n["i"] += 1
                if n["i"] <= stale_first:                       # Cloudflare still building: old index without today's edition
                    return 200, "application/json", json.dumps({"items": []}).encode()
            p = site / rel
            if p.is_file() and rel.endswith(".json"):
                return 200, "application/json", p.read_bytes()
            return 200, "text/html", b"<title>StarHub | Command Center</title>"
        return fetch

    def rt(self, **kv):
        base = {"SITE_REPO_PATH": str(self.site), "SITE_BASE_URL": "https://example.invalid", "EMAIL_SEND_ENABLED": "false", "SITE_PUSH_ENABLED": "true"}
        return self.config.Runtime(base | kv)

    def mail_rt(self, srv, **kv):
        return self.rt(EMAIL_SEND_ENABLED="true", SMTP_HOST="127.0.0.1", SMTP_PORT=str(srv.server_address[1]), SMTP_SECURITY="ssl",
                       SMTP_TLS_INSECURE_LOCAL="true", SMTP_USERNAME="u", SMTP_PASSWORD="p", EMAIL_FROM="每日一鉴 <history@read.starhub.vip>",
                       EMAIL_REPLY_TO="feedback@example.invalid.test", EMAIL_RECIPIENTS="r1@example.com,r2@example.com", **kv)

    def run_day(self, rt, date, hm="07:30", fetch=None):
        return self.publish.publish_today(self.db, rt, date=date, fetch=fetch or self.served(), clock=at(date, hm), sleep=self.slept.append)

    def remote_log(self):
        return subprocess.run(["git", "--git-dir", str(self.remote), "log", "--format=%s", "main"], capture_output=True, text=True).stdout.split("\n")

    def test_full_flow_resumes_and_never_resends(self):
        r1 = self.publish.publish_today(self.db, self.config.Runtime({"SITE_BASE_URL": "https://example.invalid"}), date="2026-11-02",
                                        fetch=self.served(), clock=at("2026-11-02"), sleep=self.slept.append)
        self.assertEqual(r1["outcome"], "waiting"); self.assertIn("SITE_REPO_PATH", r1["reason"])          # stop after archive
        body1 = Path(self.state.get(self.db, "sample-A")["path"]).read_text()
        r2 = self.run_day(self.rt(), "2026-11-02")                                                        # resume: no re-archive
        self.assertEqual(Path(self.state.get(self.db, "sample-A")["path"]).read_text(), body1)
        self.assertEqual(r2["outcome"], "waiting"); self.assertIn("EMAIL_SEND_ENABLED", r2["reason"])
        self.assertEqual((self.site / "articles.html").read_text(), "private vault")
        log = subprocess.run(["git", "-C", str(self.site), "show", "--name-only", "--format=", "HEAD"], capture_output=True, text=True).stdout.split()
        self.assertTrue(log and all(x.startswith(("history/", "data/history/")) for x in log), log)
        self.assertTrue(any(l.startswith("history: sample-A") for l in self.remote_log()))
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            srv.refuse_rcpt = {"r2@example.com"}
            r3 = self.run_day(self.mail_rt(srv), "2026-11-02")
            self.assertEqual(r3["outcome"], "partial"); self.assertEqual([d["status"] for d in r3["deliveries"]], ["accepted", "failed"])
            self.assertEqual(r3["expected_recipients"], 2)
            srv.refuse_rcpt = set(); n = len(srv.messages)
            r4 = self.run_day(self.mail_rt(srv), "2026-11-02", "08:30")
            self.assertEqual(r4["outcome"], "complete"); self.assertEqual(len(srv.messages), n + 1)       # only the failed one resent
            self.assertEqual(self.state.get(self.db, "sample-A")["status"], "complete")
        finally:
            srv.shutdown(); srv.server_close()

    def test_ineligible_edition_is_never_scheduled_and_eligibility_is_rechecked_before_each_recipient(self):
        self.ineligible.add("sample-A")                                        # e.g. its context review is no longer clean
        r = self.run_day(self.rt(), "2026-11-02")
        self.assertEqual(r["outcome"], "skipped"); self.assertEqual(self.state.get(self.db, "sample-A")["status"], "checked")
        self.ineligible.clear()
        self.run_day(self.rt(), "2026-11-02")                                     # archived + site, waiting for email
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            self.ineligible.add("sample-A")
            r = self.run_day(self.mail_rt(srv), "2026-11-02")
            self.assertEqual(r["outcome"], "waiting"); self.assertIn("not currently eligible", r["reason"]); self.assertEqual(srv.messages, [])
            from history_in_practice import final_edit
            calls = {"n": 0}; self.ineligible.clear()
            def flips(db, o, *a, **k):                                           # eligible for the first recipient, then requeued
                calls["n"] += 1
                return [] if calls["n"] <= 2 else ["requeued: context review"]
            final_edit.send_problems = flips
            r = self.run_day(self.mail_rt(srv), "2026-11-02")
            self.assertEqual([d["status"] for d in r["deliveries"]], ["accepted", "not_started_blocked"])
            self.assertEqual(len(srv.messages), 1)
        finally:
            srv.shutdown(); srv.server_close()

    def test_async_deploy_retries_with_backoff_then_sends_once(self):
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            r = self.run_day(self.mail_rt(srv), "2026-11-02", fetch=self.served(stale_first=2))
            self.assertEqual(r["outcome"], "complete"); self.assertEqual(r["live_checks"], 3); self.assertEqual(len(self.slept), 2)
            self.assertEqual(len(srv.messages), 2)
            r2 = self.run_day(self.mail_rt(srv), "2026-11-02", "09:00")                                    # rerun same day: nothing resent
            self.assertEqual(r2["outcome"], "complete"); self.assertEqual(len(srv.messages), 2)
        finally:
            srv.shutdown(); srv.server_close()

    def test_deploy_never_lands_waits_nonzero_then_overdue_and_next_day_moves_on(self):
        self.add("sample-B", "B", "world")
        never = self.served(stale_first=10_000)
        r = self.run_day(self.rt(), "2026-11-02", fetch=never)
        self.assertEqual(r["outcome"], "waiting"); self.assertEqual(self.publish.EXIT[r["outcome"]], 5)
        self.assertEqual(len(self.slept), len(self.publish.load_project()["site_wait"]["backoff_s"]))      # bounded, not forever
        r = self.run_day(self.rt(), "2026-11-02", "11:30", fetch=never)                                     # past the deadline
        self.assertEqual(r["outcome"], "overdue"); self.assertEqual(self.state.get(self.db, "sample-A")["status"], "overdue")
        r = self.run_day(self.rt(), "2026-11-03")                                                           # next day: new edition, old not resumed
        self.assertEqual(r["edition_id"], "sample-B"); self.assertEqual(self.state.get(self.db, "sample-A")["status"], "overdue")

    def test_yesterdays_partial_delivery_is_overdue_not_resent(self):
        self.add("sample-B", "B", "world")
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            srv.refuse_rcpt = {"r2@example.com"}
            self.assertEqual(self.run_day(self.mail_rt(srv), "2026-11-02")["outcome"], "partial")
            srv.refuse_rcpt = set(); n = len(srv.messages)
            r = self.run_day(self.mail_rt(srv), "2026-11-03")
            self.assertIn("sample-A", " ".join(r["overdue"])); self.assertEqual(self.state.get(self.db, "sample-A")["status"], "overdue")
            self.assertEqual(r["edition_id"], "sample-B")
            sent_a = [m for m in srv.messages[n:] if b"sample-A" in m]
            self.assertEqual(sent_a, [])                                                                    # stale email never sent late
        finally:
            srv.shutdown(); srv.server_close()

    def test_push_disabled_commit_is_pushed_once_enabled(self):
        r = self.run_day(self.rt(SITE_PUSH_ENABLED="false"), "2026-11-02")
        self.assertEqual(r["outcome"], "waiting"); self.assertIn("SITE_PUSH_ENABLED is false", r["reason"])
        self.assertFalse(any(l.startswith("history: sample-A") for l in self.remote_log()))
        r = self.run_day(self.rt(), "2026-11-02", "08:00")
        self.assertTrue(any(l.startswith("history: sample-A") for l in self.remote_log()))
        self.assertEqual(self.state.get(self.db, "sample-A")["status"], "email_pending")

    def test_empty_or_incomplete_mail_config_is_never_success(self):
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            for bad in ({"EMAIL_RECIPIENTS": ""}, {"EMAIL_REPLY_TO": ""}, {"EMAIL_RECIPIENTS": "not-an-address"}, {"SMTP_PASSWORD": ""}):
                rt = self.mail_rt(srv); rt.values.update(bad)
                r = self.run_day(rt, "2026-11-02")
                self.assertEqual(r["outcome"], "waiting", bad); self.assertIn("incomplete", r["reason"])
                self.assertEqual(self.state.get(self.db, "sample-A")["status"], "email_pending")
            self.assertEqual(len(srv.messages), 0)
        finally:
            srv.shutdown(); srv.server_close()

    def test_recipient_removed_after_freeze_keeps_edition_incomplete(self):
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            srv.refuse_rcpt = {"r2@example.com"}
            self.run_day(self.mail_rt(srv), "2026-11-02")
            srv.refuse_rcpt = set()
            rt = self.mail_rt(srv); rt.values["EMAIL_RECIPIENTS"] = "r1@example.com,r3@example.com"   # r2 removed, r3 added
            r = self.run_day(rt, "2026-11-02", "08:00")
            st = sorted(d["status"] for d in r["deliveries"])
            self.assertEqual(st, ["accepted", "missing_from_config", "not_in_frozen_set"])
            self.assertEqual(r["outcome"], "partial"); self.assertNotEqual(self.state.get(self.db, "sample-A")["status"], "complete")
        finally:
            srv.shutdown(); srv.server_close()

    def test_no_schedulable_edition_in_category_skips_and_unapproved_sample_is_not_used(self):
        self.add("sample-B", "B", "world", approval=None, origin="sample")
        self.run_day(self.rt(), "2026-11-02")
        r = self.run_day(self.rt(), "2026-11-03")                                                           # next category 'world': only an unapproved sample
        self.assertEqual(r["outcome"], "skipped"); self.assertIn("world", r["reason"])
        self.assertEqual(self.state.get(self.db, "sample-B")["status"], "checked")

    # --- the send deadline is re-checked after waits, fetches and between recipients ---------------------------

    def moving(self, date, hm):
        """A clock that advances with every injected sleep (and can be advanced by a fetch)."""
        h, m = map(int, hm.split(":")); t = {"now": datetime.fromisoformat(date).replace(hour=h, minute=m, tzinfo=LA)}
        from datetime import timedelta
        def sleep(s): self.slept.append(s); t["now"] += timedelta(seconds=s)
        def advance(s): t["now"] += timedelta(seconds=s)
        return (lambda: t["now"]), sleep, advance

    def run_moving(self, rt, date, clock, sleep, fetch):
        return self.publish.publish_today(self.db, rt, date=date, fetch=fetch, clock=clock, sleep=sleep)

    def test_sleep_never_runs_past_the_deadline_and_late_live_does_not_send(self):
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            clock, sleep, _ = self.moving("2026-11-02", "10:59")
            r = self.run_moving(self.mail_rt(srv), "2026-11-02", clock, sleep, self.served(stale_first=1))
            self.assertEqual(self.slept, [60])                       # first backoff is 60 s; the window had exactly 60 s
            # live at exactly 11:00:00 is still within the deadline (now > deadline is late) -> sends
            self.assertEqual(r["outcome"], "complete"); self.assertEqual(len(srv.messages), 2)
        finally:
            srv.shutdown(); srv.server_close()

    def test_review_scenario_1059_30_stale_then_live_after_deadline_is_not_sent(self):
        """10:59:30 stale -> (old code: sleep 60 -> 11:00:30 live -> sent). Now the wait is clamped to 30 s, and a
        sleep that overshoots the deadline (as real sleeps can) stops the loop: overdue, nothing sent."""
        import smtp_fixture
        from datetime import timedelta
        srv = smtp_fixture.start(tls=True)
        try:
            t = {"now": datetime.fromisoformat("2026-11-02").replace(hour=10, minute=59, second=30, tzinfo=LA)}
            def slp(s): self.slept.append(s); t["now"] += timedelta(seconds=s + 30)      # oversleeps by 30 s
            r = self.publish.publish_today(self.db, self.mail_rt(srv), date="2026-11-02", fetch=self.served(stale_first=1),
                                           clock=lambda: t["now"], sleep=slp)
            self.assertEqual(self.slept, [30.0])                     # clamped to the remaining window, not the 60 s backoff
            self.assertEqual(r["live_checks"], 1)                    # no fetch started after the deadline
            self.assertEqual(r["outcome"], "overdue"); self.assertEqual(len(srv.messages), 0)
            self.assertEqual(self.state.get(self.db, "sample-A")["status"], "overdue")
        finally:
            srv.shutdown(); srv.server_close()

    def test_fetch_crossing_deadline_records_live_but_sends_nothing(self):
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            clock, sleep, advance = self.moving("2026-11-02", "10:58")
            inner = self.served(stale_first=1); n = {"i": 0}
            def slow_fetch(url, timeout=20):
                if url.endswith("index.json"):
                    n["i"] += 1
                    if n["i"] == 2:
                        advance(90)                                 # 10:59 + 90 s: the successful fetch returns at 11:00:30
                return inner(url, timeout)
            r = self.run_moving(self.mail_rt(srv), "2026-11-02", clock, sleep, slow_fetch)
            self.assertEqual(r["outcome"], "overdue"); self.assertIn("went live", r["reason"])
            self.assertEqual(len(srv.messages), 0); self.assertEqual(self.state.get(self.db, "sample-A")["status"], "overdue")
            notes = [x[0] for x in self.db.execute("SELECT to_status FROM transition WHERE edition_id='sample-A' ORDER BY id")]
            self.assertIn("site_live", notes)                       # the site did go live: recorded, not hidden
            r2 = self.run_moving(self.mail_rt(srv), "2026-11-02", clock, sleep, self.served())
            self.assertEqual(len(srv.messages), 0)                   # rerun later that day: still nothing sent
        finally:
            srv.shutdown(); srv.server_close()

    def test_deadline_between_recipients_keeps_first_result_and_sends_no_more(self):
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            clock, sleep, advance = self.moving("2026-11-02", "10:59")
            from history_in_practice import mailer
            real = mailer.send_one
            def slow_send(cfg, msg, rcpt, timeout=30):
                out = real(cfg, msg, rcpt, timeout); advance(120); return out   # first SMTP exchange ends at 11:01
            mailer.send_one = slow_send
            try:
                r = self.run_moving(self.mail_rt(srv), "2026-11-02", clock, sleep, self.served())
            finally:
                mailer.send_one = real
            self.assertEqual(r["outcome"], "overdue"); self.assertEqual(len(srv.messages), 1)
            st = sorted(d["status"] for d in r["deliveries"]); self.assertEqual(st, ["accepted", "not_started_deadline"])
            acc = self.db.execute("SELECT status FROM delivery WHERE edition_id='sample-A'").fetchall()
            self.assertEqual([a[0] for a in acc], ["accepted"])     # the accepted one stays accepted; the other has no send record
            self.assertEqual(self.state.get(self.db, "sample-A")["status"], "overdue")
        finally:
            srv.shutdown(); srv.server_close()


if __name__ == "__main__":
    unittest.main()

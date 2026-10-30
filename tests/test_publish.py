import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src")); sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).resolve().parents[1]


class PublishFlow(unittest.TestCase):
    """End-to-end daily flow with local fixtures: temp content dir, temp website git repo,
    live check served from that repo, local SMTPS. Proves resume-after-crash and no resend."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); t = Path(self.td.name)
        os.environ["HIP_DATA_DIR"] = str(t / "data"); os.environ["HIP_CONTENT_DIR"] = str(t / "content")
        from history_in_practice import state, publish, config, render
        self.state, self.publish, self.config, self.render = state, publish, config, render
        self.db = state.connect(t / "data" / "s.sqlite")
        self.site = t / "site"; self.site.mkdir()
        (self.site / "articles.html").write_text("private vault"); (self.site / "index.html").write_text("home")
        subprocess.run(["git", "init", "-q", str(self.site)], check=True)
        for k, v in (("user.email", "t@example.invalid"), ("user.name", "t")):
            subprocess.run(["git", "-C", str(self.site), "config", k, v], check=True)
        subprocess.run(["git", "-C", str(self.site), "add", "-A"], check=True); subprocess.run(["git", "-C", str(self.site), "commit", "-qm", "init"], check=True)
        art = t / "drafts" / "sample-A.json"; art.parent.mkdir(parents=True); shutil.copy(ROOT / "samples/A/article.json", art)
        state.transition(self.db, "sample-A", "prepared", category="china_ancient", path=str(art))
        o = json.loads(art.read_text()); render.finalize(o)
        state.transition(self.db, "sample-A", "checked", content_sha256=o["content_sha256"])

    def tearDown(self):
        self.td.cleanup(); os.environ.pop("HIP_DATA_DIR"); os.environ.pop("HIP_CONTENT_DIR")

    def served(self):
        site = self.site
        def fetch(url, timeout=20):
            rel = url.split("://", 1)[1].split("/", 1)[1]
            p = site / rel
            if p.is_file() and rel.endswith(".json"):
                return 200, "application/json", p.read_bytes()
            return 200, "text/html", b"<title>StarHub | Command Center</title>"
        return fetch

    def rt(self, **kv):
        base = {"SITE_REPO_PATH": str(self.site), "SITE_BASE_URL": "https://example.invalid", "EMAIL_SEND_ENABLED": "false"}
        return self.config.Runtime(base | kv)

    def test_full_flow_resumes_and_never_resends(self):
        p = self.publish
        r1 = p.publish_today(self.db, self.config.Runtime({"SITE_BASE_URL": "https://example.invalid"}), date="2026-11-02", fetch=self.served())
        self.assertEqual(r1["outcome"], "waiting"); self.assertIn("SITE_REPO_PATH", r1["reason"])          # crash/stop after archive
        archived = self.state.get(self.db, "sample-A"); body1 = Path(archived["path"]).read_text()
        r2 = p.publish_today(self.db, self.rt(), date="2026-11-02", fetch=self.served())                       # resume: no re-archive
        self.assertEqual(Path(self.state.get(self.db, "sample-A")["path"]).read_text(), body1)
        self.assertEqual(r2["outcome"], "waiting"); self.assertIn("EMAIL_SEND_ENABLED", r2["reason"])
        self.assertEqual((self.site / "articles.html").read_text(), "private vault")
        log = subprocess.run(["git", "-C", str(self.site), "show", "--name-only", "--format=", "HEAD"], capture_output=True, text=True).stdout.split()
        self.assertTrue(log and all(x.startswith(("history/", "data/history/")) for x in log), log)
        import smtp_fixture
        srv = smtp_fixture.start(tls=True)
        try:
            rt = self.rt(EMAIL_SEND_ENABLED="true", SMTP_HOST="127.0.0.1", SMTP_PORT=str(srv.server_address[1]), SMTP_SECURITY="ssl",
                         SMTP_TLS_INSECURE_LOCAL="true", EMAIL_FROM="每日一鉴 <history@read.starhub.vip>",
                         EMAIL_RECIPIENTS="r1@example.invalid,r2@example.invalid")
            srv.refuse_rcpt = {"r2@example.invalid"}
            r3 = p.publish_today(self.db, rt, date="2026-11-02", fetch=self.served())
            self.assertEqual(r3["outcome"], "partial"); self.assertEqual([d["status"] for d in r3["deliveries"]], ["accepted", "failed"])
            srv.refuse_rcpt = set(); n = len(srv.messages)
            r4 = p.publish_today(self.db, rt, date="2026-11-02", fetch=self.served())
            self.assertEqual(r4["outcome"], "complete"); self.assertEqual(len(srv.messages), n + 1)    # only the failed one resent
            self.assertEqual(self.state.get(self.db, "sample-A")["status"], "complete")
        finally:
            srv.shutdown(); srv.server_close()

    def test_stale_live_site_blocks_email(self):
        self.publish.publish_today(self.db, self.rt(), date="2026-11-02", fetch=self.served())
        st = self.state.get(self.db, "sample-A")["status"]; self.assertEqual(st, "email_pending")
        # a second edition whose site check sees an old copy must stay site_committed
        art = Path(self.td.name) / "drafts" / "x.json"; o = json.loads((ROOT / "samples/B/article.json").read_text()); art.write_text(json.dumps(o))
        self.render.finalize(o); art.write_text(json.dumps(o))
        self.state.transition(self.db, "sample-B", "prepared", category="world", path=str(art))
        self.state.transition(self.db, "sample-B", "checked", content_sha256=o["content_sha256"])
        stale = {"items": [{"edition_id": "sample-B", "revision": 1, "path": "data/history/old.json"}]}
        def fetch(url, timeout=20):
            if url.endswith("index.json"): return 200, "application/json", json.dumps(stale).encode()
            if url.endswith("old.json"):
                old = dict(o); old["content_sha256"] = "0" * 64; return 200, "application/json", json.dumps(old).encode()
            return 200, "text/html", b"home"
        r = self.publish.publish_today(self.db, self.rt(), date="2026-11-03", fetch=fetch)
        self.assertEqual(r["outcome"], "waiting"); self.assertIn("live check failed", r["reason"])
        self.assertEqual(self.state.get(self.db, "sample-B")["status"], "site_committed")

    def test_no_checked_edition_in_category_skips(self):
        r = self.publish.publish_today(self.db, self.rt(), date="2026-11-02", fetch=self.served())
        r = self.publish.publish_today(self.db, self.rt(), date="2026-11-03", fetch=self.served())      # next category is 'world': none ready
        self.assertEqual(r["outcome"], "skipped"); self.assertIn("world", r["reason"])


if __name__ == "__main__":
    unittest.main()

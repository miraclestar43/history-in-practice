"""One tracked TEST edition: persisted identity, labels only, site preview before email, no resend, bounded window,
and no effect on production edition/rotation state. The real CLI runs against a local SMTPS server and a local
HTTP server that serves the exported preview."""
import functools, http.server, json, os, sqlite3, subprocess, sys, tempfile, threading, time, unittest
from email import message_from_bytes, policy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import smtp_fixture
from history_in_practice import testrun, state, render
ROOT = Path(__file__).resolve().parents[1]
ART = str(ROOT / "samples/auto/cand-20261030-snow-water-companies/final/article.json")
TID = "test-20261030-snow"


def serve(root):
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(Q, directory=str(root))
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h); threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


class Unit(unittest.TestCase):
    def setUp(self):
        self.db = state.connect(Path(tempfile.mkdtemp()) / "t.sqlite")

    def test_labels_only_and_identity_is_reused(self):
        rec, t = testrun.create_or_load(self.db, TID, Path(ART), site_base="http://x", window_hours=2, now=1000)
        src = json.loads(Path(ART).read_text())
        self.assertEqual(testrun.body_problems(src, t), [])
        self.assertTrue(t["title"]["zh"].startswith("【测试】") and t["title"]["en"].startswith("[TEST] "))
        self.assertEqual(t["status"], "test"); self.assertNotEqual(t["content_sha256"], src["content_sha256"])
        rec2, t2 = testrun.create_or_load(self.db, TID, Path(ART), site_base="http://x", window_hours=9, now=99999)
        self.assertEqual((rec2["created_at"], rec2["window_expires"], t2["content_sha256"]), (rec["created_at"], rec["window_expires"], t["content_sha256"]))
        self.assertIsNone(state.get(self.db, TID)); self.assertIsNone(state.get(self.db, src["edition_id"]))   # no production rows

    def test_different_article_or_preview_under_same_id_is_refused(self):
        testrun.create_or_load(self.db, TID, Path(ART), site_base="http://x", window_hours=2)
        other = ROOT / "samples/auto/cand-20261030-darwin-wallace/final/article.json"
        with self.assertRaises(testrun.TestRunError): testrun.create_or_load(self.db, TID, other, site_base="http://x", window_hours=2)
        with self.assertRaises(testrun.TestRunError): testrun.create_or_load(self.db, TID, Path(ART), site_base="http://y", window_hours=2)
        with self.assertRaises(testrun.TestRunError): testrun.create_or_load(self.db, "test-x", Path(ART), site_base="http://x", window_hours=2)
        with self.assertRaises(testrun.TestRunError): testrun.create_or_load(self.db, "test-20261030-b", Path(ART), site_base="", window_hours=48)

    def test_edited_body_is_detected(self):
        src = json.loads(Path(ART).read_text()); t = testrun.make_test_obj(src, TID, "2026-10-30")
        t["sections"][1]["paras"][0]["en"] += " Invented."
        self.assertIn("sections differs from the source article", testrun.body_problems(src, t))

    def test_window_renewal_only_before_anything_was_sent(self):
        rec, t = testrun.create_or_load(self.db, TID, Path(ART), site_base="http://x", window_hours=1, now=1000)
        self.assertTrue(testrun.window_open(rec, 1000 + 3599)); self.assertFalse(testrun.window_open(rec, 1000 + 3600))
        testrun.renew_window(self.db, TID, 2)
        state.set_delivery(self.db, TID, t["revision"], "k", "r***", "unknown")
        with self.assertRaises(testrun.TestRunError): testrun.renew_window(self.db, TID, 2)


class Cli(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); self.smtp = smtp_fixture.start(tls=True)
        self.site = Path(self.td.name) / "site"; self.site.mkdir(); self.http = serve(self.site)
        self.base = f"http://127.0.0.1:{self.http.server_address[1]}"

    def tearDown(self):
        for s in (self.smtp, self.http): s.shutdown(); s.server_close()
        self.td.cleanup()

    def hip(self, *args, **over):
        env_file = Path(self.td.name) / "runtime.env"
        vals = {"SMTP_HOST": "127.0.0.1", "SMTP_PORT": str(self.smtp.server_address[1]), "SMTP_SECURITY": "ssl", "SMTP_TLS_INSECURE_LOCAL": "true",
                "SMTP_USERNAME": "u", "SMTP_PASSWORD": "p", "EMAIL_FROM": "每日一鉴 <history@read.starhub.vip>",
                "EMAIL_REPLY_TO": "feedback@example.com", "EMAIL_RECIPIENTS": "r1@example.com,r2@example.com", "EMAIL_SEND_ENABLED": "false"}
        vals.update(over); env_file.write_text("".join(f"{k}={v}\n" for k, v in vals.items())); env_file.chmod(0o600)
        r = subprocess.run([str(ROOT / "bin/hip"), *args], capture_output=True, text=True,
                           env=dict(os.environ, HIP_DATA_DIR=str(Path(self.td.name) / "data"), HIP_RUNTIME_ENV=str(env_file)))
        try:
            return r.returncode, json.loads(r.stdout) if r.stdout.strip() else {}, r.stderr
        except ValueError:
            return r.returncode, {}, r.stdout + r.stderr

    def test_retired_send_test_refuses(self):
        rc, _, err = self.hip("send-test", ART, "--confirm-real-email"); self.assertNotEqual(rc, 0); self.assertIn("test-edition", err)
        self.assertEqual(self.smtp.messages, [])

    def test_site_first_then_one_send_per_recipient_and_no_resend(self):
        rc, out, err = self.hip("test-edition", "prepare", ART, "--test-id", TID, "--site-base", self.base, "--window-hours", "2")
        self.assertEqual(rc, 0, err)
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email")
        self.assertEqual(rc, 2); self.assertIn("site preview", out["reason"]); self.assertEqual(self.smtp.messages, [])  # nothing deployed yet
        rc, out, _ = self.hip("test-edition", "prepare", ART, "--test-id", TID, "--site-base", self.base, "--site-root", str(self.site))
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email", EMAIL_REPLY_TO="")
        self.assertEqual(rc, 2); self.assertIn("EMAIL_REPLY_TO", out["reason"]); self.assertEqual(self.smtp.messages, [])
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID)
        self.assertNotEqual(rc, 0); self.assertEqual(self.smtp.messages, [])                                       # confirmation required
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email")
        self.assertEqual(rc, 0, out); self.assertTrue(out["all_accepted"]); self.assertEqual(len(self.smtp.messages), 2)
        m = message_from_bytes(self.smtp.messages[0][1], policy=policy.default)
        self.assertIn("【测试】", m["Subject"]); self.assertIn(TID, m["X-HIP-Edition"])
        body = m.get_body(("plain",)).get_content(); self.assertIn("测试 TEST", body); self.assertIn(self.base + "/history/?story=" + TID, body)
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email")
        self.assertEqual(len(self.smtp.messages), 2); self.assertTrue(all("skipped" in r["action"] for r in out["report"]))
        self.assertNotIn("r1@example.com", json.dumps(out)); self.assertNotIn("r2@example.com", json.dumps(out))
        db = sqlite3.connect(Path(self.td.name) / "data/hip.sqlite")
        self.assertEqual(db.execute("SELECT count(*) FROM edition").fetchone()[0], 0)                               # no production state

    def test_failed_recipient_retries_under_same_identity_unknown_does_not(self):
        self.hip("test-edition", "prepare", ART, "--test-id", TID, "--site-base", self.base, "--site-root", str(self.site))
        self.smtp.refuse_rcpt = {"r1@example.com"}; self.smtp.drop_in_data = {"r2@example.com"}
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email")
        self.assertEqual(rc, 3); self.assertEqual(sorted(r["status"] for r in out["report"]), ["failed", "unknown"])
        self.smtp.refuse_rcpt = set(); self.smtp.drop_in_data = set(); n = len(self.smtp.messages)
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email")
        self.assertEqual(len(self.smtp.messages), n + 1); self.assertEqual(self.smtp.messages[-1][0], "r1@example.com")
        self.assertEqual(sorted(d["status"] for d in out["deliveries"]), ["accepted", "unknown"]); self.assertEqual(rc, 3)
        rc, out, _ = self.hip("test-edition", "renew-window", "--test-id", TID, "--window-hours", "1")
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

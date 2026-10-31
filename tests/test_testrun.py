"""One tracked TEST edition: persisted identity, labels only, site preview before email, no resend, bounded window,
no effect on production edition/rotation state, and the source must be admitted *now* (at prepare, at send and before
each recipient: unregistered, requeued, changed evidence/record/article are refused; accepted/unknown stay as recorded). The real CLI runs against a local SMTPS server and a local
HTTP server that serves the exported preview."""
import fcntl, functools, http.server, json, os, shutil, sqlite3, subprocess, sys, tempfile, threading, time, unittest
from email import message_from_bytes, policy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import smtp_fixture
from history_in_practice import testrun, state, render, editor, context
ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "tests/fixtures/admitted_final"          # pinned copy of the Snow final as first admitted (the live sample is being repaired)
TID = "test-20261030-snow"


def admitted_copy(td: Path, db) -> Path:
    """A copy of the real admitted Snow final (article, evidence, base, final-editor record), registered as admitted in
    this test's database exactly as final_edit.admit leaves it (path, revision, content hash, approval naming the record)."""
    d = td / "final"; shutil.copytree(REAL, d)
    o = json.loads((d / "article.json").read_text()); rec = json.loads((d / "final_editor_record.json").read_text())
    ev = json.loads((d / "evidence.json").read_text())                 # LABELLED FIXTURE context record (no source units): the
    (d / "context_review.json").write_text(json.dumps({                # context review itself is tested in test_context.py
        "record_type": "context_review", "schema": context.SCHEMA, "mode": "article", "fixture": True, "edition_id": o["edition_id"],
        "content_sha256": o["content_sha256"], "evidence_in_sha256": editor.sha(ev), "evidence_sha256": editor.sha(ev), "outcome": "clean",
        "blocking": [], "units": {}, "claims": [dict(f, verdict="supported", scope="fixture", source_ids=[]) for f in context.absence_claims(o)]},
        ensure_ascii=False))
    for s in ("pending_review", "prepared"):
        state.transition(db, o["edition_id"], s)
    state.transition(db, o["edition_id"], "checked", path=str(d / "article.json"), content_sha256=o["content_sha256"], revision=o["revision"],
                     approval=f"final-editor: fixture; record {editor.sha(rec)[:12]}", origin="pipeline")
    return d / "article.json"


def serve(root):
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(Q, directory=str(root))
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h); threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


class Unit(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp()); self.db = state.connect(self.td / "t.sqlite"); self.art = admitted_copy(self.td, self.db)

    def test_labels_only_and_identity_is_reused(self):
        rec, t = testrun.create_or_load(self.db, TID, self.art, site_base="http://x", window_hours=2, now=1000)
        src = json.loads(self.art.read_text())
        self.assertEqual(testrun.body_problems(src, t), [])
        self.assertTrue(t["title"]["zh"].startswith("【测试】") and t["title"]["en"].startswith("[TEST] "))
        self.assertEqual(t["status"], "test"); self.assertNotEqual(t["content_sha256"], src["content_sha256"])
        rec2, t2 = testrun.create_or_load(self.db, TID, self.art, site_base="http://x", window_hours=9, now=99999)
        self.assertEqual((rec2["created_at"], rec2["window_expires"], t2["content_sha256"]), (rec["created_at"], rec["window_expires"], t["content_sha256"]))
        self.assertIsNone(state.get(self.db, TID)); self.assertEqual(state.get(self.db, src["edition_id"])["status"], "checked")  # untouched

    def test_different_article_or_preview_under_same_id_is_refused(self):
        testrun.create_or_load(self.db, TID, self.art, site_base="http://x", window_hours=2)
        other = ROOT / "samples/auto/cand-20261030-darwin-wallace/final/article.json"
        with self.assertRaises(testrun.TestRunError): testrun.create_or_load(self.db, TID, other, site_base="http://x", window_hours=2)
        with self.assertRaises(testrun.TestRunError):          # admitted elsewhere doesn't matter: this db never admitted it
            testrun.create_or_load(self.db, "test-20261030-other", other, site_base="http://x", window_hours=2)
        with self.assertRaises(testrun.TestRunError): testrun.create_or_load(self.db, TID, self.art, site_base="http://y", window_hours=2)
        with self.assertRaises(testrun.TestRunError): testrun.create_or_load(self.db, "test-x", self.art, site_base="http://x", window_hours=2)
        with self.assertRaises(testrun.TestRunError): testrun.create_or_load(self.db, "test-20261030-b", self.art, site_base="", window_hours=48)

    def test_unregistered_or_unadmitted_source_is_refused_at_prepare(self):
        db = state.connect(self.td / "empty.sqlite")
        with self.assertRaisesRegex(testrun.TestRunError, "not a registered edition"):
            testrun.create_or_load(db, TID, self.art, site_base="http://x", window_hours=2)
        o = json.loads(self.art.read_text()); state.transition(db, o["edition_id"], "pending_review")
        with self.assertRaisesRegex(testrun.TestRunError, "pending_review, not admitted"):
            testrun.create_or_load(db, TID, self.art, site_base="http://x", window_hours=2)
        self.assertIsNone(testrun.get(db, TID))                                                    # nothing persisted
        copy = self.td / "elsewhere.json"; shutil.copy(self.art, copy)                              # same content, not the admitted file
        with self.assertRaisesRegex(testrun.TestRunError, "not the admitted article"):
            testrun.create_or_load(self.db, TID, copy, site_base="http://x", window_hours=2)

    def test_changed_evidence_record_or_article_after_prepare_blocks(self):
        rec, _ = testrun.create_or_load(self.db, TID, self.art, site_base="http://x", window_hours=2)
        sp = lambda: testrun.source_problems(self.db, rec["source_edition"], rec["source_sha256"])
        self.assertEqual(sp(), [])
        d = self.art.parent
        for name, mutate, want in (
                ("evidence.json", lambda x: x["excerpts"][0].update(quote=x["excerpts"][0]["quote"] + "，"), "evidence differs"),
                ("final_editor_record.json", lambda x: x.update(rounds=x["rounds"][:-1] + [dict(x["rounds"][-1], verify={})]), "record"),
                ("article.json", lambda x: x["sections"][0]["paras"][0].update(zh=x["sections"][0]["paras"][0]["zh"] + "。"), "differs")):
            keep = (d / name).read_text(); x = json.loads(keep); mutate(x); (d / name).write_text(json.dumps(x, ensure_ascii=False))
            with self.subTest(name):
                self.assertTrue(any(want in p for p in sp()), sp())
            (d / name).write_text(keep)
        self.assertEqual(sp(), [])

    def test_requeued_source_never_reaches_transport(self):
        rec, test = testrun.create_or_load(self.db, TID, self.art, site_base="http://x", window_hours=2)
        calls = []; o = json.loads(self.art.read_text())
        state.transition(self.db, o["edition_id"], "pending_review", reason="requeued: factual defect")
        orig = (testrun.verify_site, testrun.mailer.validate_config, testrun.mailer.send_edition)
        testrun.verify_site = lambda *a, **k: (True, []); testrun.mailer.validate_config = lambda r: []
        testrun.mailer.send_edition = lambda *a, **k: calls.append(1) or []
        try:
            r = testrun.send(self.db, rec, test, None, base="http://x", out=self.td / "out")
        finally:
            testrun.verify_site, testrun.mailer.validate_config, testrun.mailer.send_edition = orig
        self.assertFalse(r["sent"]); self.assertIn("pending_review, not admitted", r["reason"]); self.assertEqual(calls, [])

    def test_edited_body_is_detected(self):
        src = json.loads(self.art.read_text()); t = testrun.make_test_obj(src, TID, "2026-10-30")
        t["sections"][1]["paras"][0]["en"] += " Invented."
        self.assertIn("sections differs from the source article", testrun.body_problems(src, t))

    def test_window_renewal_only_before_anything_was_sent(self):
        rec, t = testrun.create_or_load(self.db, TID, self.art, site_base="http://x", window_hours=1, now=1000)
        self.assertTrue(testrun.window_open(rec, 1000 + 3599)); self.assertFalse(testrun.window_open(rec, 1000 + 3600))
        testrun.renew_window(self.db, TID, 2)
        state.set_delivery(self.db, TID, t["revision"], "k", "r***", "unknown")
        with self.assertRaises(testrun.TestRunError): testrun.renew_window(self.db, TID, 2)


class Cli(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); self.smtp = smtp_fixture.start(tls=True)
        (Path(self.td.name) / "data").mkdir(); self.db = state.connect(Path(self.td.name) / "data/hip.sqlite")
        self.art = str(admitted_copy(Path(self.td.name), self.db))
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
        rc, _, err = self.hip("send-test", self.art, "--confirm-real-email"); self.assertNotEqual(rc, 0); self.assertIn("test-edition", err)
        self.assertEqual(self.smtp.messages, [])

    def test_site_first_then_one_send_per_recipient_and_no_resend(self):
        rc, out, err = self.hip("test-edition", "prepare", self.art, "--test-id", TID, "--site-base", self.base, "--window-hours", "2")
        self.assertEqual(rc, 0, err)
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email")
        self.assertEqual(rc, 2); self.assertIn("site preview", out["reason"]); self.assertEqual(self.smtp.messages, [])  # nothing deployed yet
        rc, out, _ = self.hip("test-edition", "prepare", self.art, "--test-id", TID, "--site-base", self.base, "--site-root", str(self.site))
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email", EMAIL_REPLY_TO="")
        self.assertEqual(rc, 2); self.assertIn("EMAIL_REPLY_TO", out["reason"]); self.assertEqual(self.smtp.messages, [])
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID)
        self.assertNotEqual(rc, 0); self.assertEqual(self.smtp.messages, [])                                       # confirmation required
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email")
        self.assertEqual(rc, 0, out); self.assertTrue(out["all_accepted"]); self.assertEqual(len(self.smtp.messages), 2)
        m = message_from_bytes(self.smtp.messages[0][1], policy=policy.default)
        self.assertIn("【测试】", m["Subject"]); self.assertIn(TID, m["X-HIP-Edition"])
        self.assertRegex(m["Subject"], r"^没事儿多读书｜\d{4}\.\d{2}\.\d{2}｜【测试】")                  # column｜edition date (LA)｜title
        self.assertEqual(m["From"].addresses[0].display_name, "没事儿多读书"); self.assertEqual(m["From"].addresses[0].addr_spec, "history@read.starhub.vip")
        body = m.get_body(("plain",)).get_content(); self.assertIn("测试 TEST", body); self.assertIn(self.base + "/history/?story=" + TID, body)
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email")
        self.assertEqual(len(self.smtp.messages), 2); self.assertTrue(all("skipped" in r["action"] for r in out["report"]))
        self.assertNotIn("r1@example.com", json.dumps(out)); self.assertNotIn("r2@example.com", json.dumps(out))
        db = sqlite3.connect(Path(self.td.name) / "data/hip.sqlite")                               # production state untouched:
        self.assertEqual(db.execute("SELECT edition_id, status FROM edition").fetchall(), [("cand-20261030-snow-water-companies", "checked")])

    def test_failed_recipient_retries_under_same_identity_unknown_does_not(self):
        self.hip("test-edition", "prepare", self.art, "--test-id", TID, "--site-base", self.base, "--site-root", str(self.site))
        self.smtp.refuse_rcpt = {"r1@example.com"}; self.smtp.drop_in_data = {"r2@example.com"}
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email")
        self.assertEqual(rc, 3); self.assertEqual(sorted(r["status"] for r in out["report"]), ["failed", "unknown"])
        self.smtp.refuse_rcpt = set(); self.smtp.drop_in_data = set(); n = len(self.smtp.messages)
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email")
        self.assertEqual(len(self.smtp.messages), n + 1); self.assertEqual(self.smtp.messages[-1][0], "r1@example.com")
        self.assertEqual(sorted(d["status"] for d in out["deliveries"]), ["accepted", "unknown"]); self.assertEqual(rc, 3)
        rc, out, _ = self.hip("test-edition", "renew-window", "--test-id", TID, "--window-hours", "1")
        self.assertNotEqual(rc, 0)

    def test_requeue_after_partial_send_blocks_the_rest_and_keeps_accepted(self):
        self.hip("test-edition", "prepare", self.art, "--test-id", TID, "--site-base", self.base, "--site-root", str(self.site))
        self.smtp.refuse_rcpt = {"r1@example.com"}
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email")
        self.assertEqual(sorted(r["status"] for r in out["report"]), ["accepted", "failed"]); n = len(self.smtp.messages)
        lk = open(Path(self.td.name) / "data/publish.lock", "w"); fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)   # a send in progress
        rc, out, err = self.hip("requeue", "cand-20261030-snow-water-companies", "--reason", "factual defect")
        self.assertNotEqual(rc, 0); self.assertIn("another publish job", err)
        fcntl.flock(lk, fcntl.LOCK_UN); lk.close()
        rc, out, _ = self.hip("requeue", "cand-20261030-snow-water-companies", "--reason", "factual defect"); self.assertEqual(rc, 0)
        self.smtp.refuse_rcpt = set()
        rc, out, _ = self.hip("test-edition", "send", "--test-id", TID, "--confirm-real-email")
        self.assertEqual(rc, 2); self.assertIn("not currently admitted", out["reason"]); self.assertEqual(len(self.smtp.messages), n)
        rc, out, _ = self.hip("test-edition", "status", "--test-id", TID)
        self.assertFalse(out["source_admitted_now"]); self.assertEqual(sorted(d["status"] for d in out["deliveries"]), ["accepted", "failed"])


if __name__ == "__main__":
    unittest.main()

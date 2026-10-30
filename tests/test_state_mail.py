import json, ssl, sys, tempfile, unittest
from email import message_from_bytes
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src")); sys.path.insert(0, str(Path(__file__).parent))
from history_in_practice import state, mailer, render, config
import smtp_fixture

ROOT = Path(__file__).resolve().parents[1]
OBJ = json.loads((ROOT / "samples/B/article.json").read_text())
FAKE = ["a@example.invalid", "b@example.invalid", "c@example.invalid"]


def client_cfg(port):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    return {"host": "127.0.0.1", "port": port, "security": "ssl", "username": "u", "password": "p", "ssl_context": ctx, "from": "history@read.starhub.vip"}


class MailState(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); self.db = state.connect(Path(self.td.name) / "t.sqlite")
        render.finalize(OBJ); out = Path(self.td.name) / "r"; render.build([dict(OBJ)], out, "https://starhub.vip")
        self.html = (out / "email" / f"{OBJ['edition_id']}.html").read_text(); self.text = (out / "email" / f"{OBJ['edition_id']}.txt").read_text()
        self.srv = smtp_fixture.start(tls=True)

    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close(); self.td.cleanup()

    def send(self, rcpts):
        return mailer.send_edition(self.db, OBJ, self.html, self.text, None, mode="local-test",
                                   smtp_cfg=client_cfg(self.srv.server_address[1]), recipients=rcpts)

    def test_one_accepted_one_refused_one_unknown_then_no_blind_resend(self):
        self.srv.refuse_rcpt = {FAKE[1]}; self.srv.drop_in_data = {FAKE[2]}
        rep = self.send(FAKE)
        self.assertEqual([r["status"] for r in rep], ["accepted", "failed", "unknown"])
        self.assertNotIn("example.invalid", json.dumps(rep))           # reports never contain addresses
        n = len(self.srv.messages)
        self.srv.refuse_rcpt = set(); self.srv.drop_in_data = set()
        rep2 = self.send(FAKE)                                        # rerun: only the failed one is attempted
        self.assertEqual([r["status"] for r in rep2], ["accepted", "accepted", "unknown"])
        self.assertEqual(len(self.srv.messages), n + 1)
        self.assertTrue(rep2[0]["action"].startswith("skipped") and rep2[2]["action"].startswith("skipped"))

    def test_message_is_multipart_utf8_with_stable_message_id(self):
        self.send(FAKE[:1]); body = self.srv.messages[0][1]
        m = message_from_bytes(body)
        self.assertEqual(m.get_content_type(), "multipart/alternative")
        self.assertEqual([p.get_content_type() for p in m.get_payload()], ["text/plain", "text/html"])
        k = state.recipient_key(FAKE[0])
        self.assertEqual(m["Message-ID"], mailer.message_id(OBJ["edition_id"], OBJ["revision"], k, "read.starhub.vip"))
        self.assertIn(OBJ["content_sha256"][:12], m["X-HIP-Edition"])
        html = [p for p in m.get_payload() if p.get_content_type() == "text/html"][0].get_payload(decode=True).decode()
        self.assertIn(OBJ["title"]["en"].split(":")[0], html)   # English edition present, not truncated away
        self.assertIn(OBJ["title"]["zh"][:6], html)

    def test_crash_while_sending_becomes_unknown_and_is_not_retried(self):
        k = state.recipient_key(FAKE[0])
        state.set_delivery(self.db, OBJ["edition_id"], OBJ["revision"], k, "x", "sending", bump=True)
        self.assertEqual(len(state.recover(self.db)), 1)
        rep = self.send(FAKE[:1])
        self.assertEqual(rep[0]["status"], "unknown"); self.assertEqual(len(self.srv.messages), 0)

    def test_real_mode_refuses_when_disabled_and_local_mode_refuses_remote_hosts(self):
        rt = config.Runtime({"EMAIL_SEND_ENABLED": "false", "EMAIL_RECIPIENTS": "x@example.invalid"})
        with self.assertRaises(mailer.SendDisabled):
            mailer.send_edition(self.db, OBJ, self.html, self.text, rt, mode="real")
        with self.assertRaises(mailer.SendDisabled):
            mailer.send_edition(self.db, OBJ, self.html, self.text, None, mode="local-test",
                                smtp_cfg={"host": "smtp.resend.com", "port": 465}, recipients=FAKE)

    def full_rt(self, **kv):
        base = {"EMAIL_SEND_ENABLED": "true", "SMTP_HOST": "127.0.0.1", "SMTP_PORT": str(self.srv.server_address[1]), "SMTP_SECURITY": "ssl",
                "SMTP_TLS_INSECURE_LOCAL": "true", "SMTP_USERNAME": "u", "SMTP_PASSWORD": "p", "EMAIL_FROM": "每日一鉴 <history@read.starhub.vip>",
                "EMAIL_REPLY_TO": "feedback@example.com", "EMAIL_RECIPIENTS": "r1@example.com,r2@example.com"}
        return config.Runtime(base | kv)

    def test_incomplete_config_and_empty_recipients_never_report_success(self):
        for bad, needle in (({"EMAIL_RECIPIENTS": ""}, "empty"), ({"EMAIL_RECIPIENTS": "a@example.com,bogus"}, "malformed"),
                            ({"EMAIL_RECIPIENTS": "a@example.com,A@example.com"}, "duplicate"), ({"EMAIL_REPLY_TO": ""}, "REPLY_TO"),
                            ({"SMTP_PASSWORD": ""}, "SMTP_PASSWORD"), ({"EMAIL_FROM": "nobody"}, "EMAIL_FROM")):
            with self.assertRaises(mailer.ConfigIncomplete) as cm:
                mailer.send_edition(self.db, OBJ, self.html, self.text, self.full_rt(**bad), mode="real")
            self.assertIn(needle, str(cm.exception)); self.assertNotIn("example.com", str(cm.exception).replace("example.com>", ""))
        with self.assertRaises(mailer.ConfigIncomplete):
            mailer.send_edition(self.db, OBJ, self.html, self.text, None, mode="local-test", smtp_cfg=client_cfg(self.srv.server_address[1]), recipients=[])
        self.assertFalse(state.delivery_complete(self.db, OBJ["edition_id"], OBJ["revision"]))       # nothing frozen: never complete
        self.assertEqual(len(self.srv.messages), 0)

    def test_completion_is_over_the_frozen_expected_set(self):
        rep = mailer.send_edition(self.db, OBJ, self.html, self.text, self.full_rt(), mode="real")
        self.assertEqual([r["status"] for r in rep], ["accepted", "accepted"])
        self.assertTrue(state.delivery_complete(self.db, OBJ["edition_id"], OBJ["revision"]))
        state.freeze_recipients(self.db, "other", 1, ["a@example.com", "b@example.com"])
        state.set_delivery(self.db, "other", 1, state.recipient_key("a@example.com"), "a", "accepted")
        self.assertFalse(state.delivery_complete(self.db, "other", 1))                                # one of two frozen accepted

    def test_manual_test_send_works_while_disabled_but_needs_full_config(self):
        rt = self.full_rt(EMAIL_SEND_ENABLED="false")
        with self.assertRaises(mailer.SendDisabled):
            mailer.send_edition(self.db, OBJ, self.html, self.text, rt, mode="real")
        rep = mailer.send_edition(self.db, OBJ, self.html, self.text, rt, mode="real", manual_test=True)
        self.assertEqual([r["status"] for r in rep], ["accepted", "accepted"])
        with self.assertRaises(mailer.ConfigIncomplete):
            mailer.send_edition(self.db, OBJ, self.html, self.text, self.full_rt(EMAIL_SEND_ENABLED="false", EMAIL_REPLY_TO=""), mode="real", manual_test=True)
        m = message_from_bytes(self.srv.messages[0][1]); self.assertEqual(m["Reply-To"], "feedback@example.com")

    def test_connect_failure_is_failed_not_unknown(self):
        cfg = client_cfg(1)   # nothing listens on port 1
        rep = mailer.send_edition(self.db, OBJ, self.html, self.text, None, mode="local-test", smtp_cfg=cfg, recipients=FAKE[:1])
        self.assertEqual(rep[0]["status"], "failed")


class EditionState(unittest.TestCase):
    def test_transitions_and_frozen_content(self):
        with tempfile.TemporaryDirectory() as td:
            db = state.connect(Path(td) / "s.sqlite")
            state.transition(db, "e1", "prepared"); state.transition(db, "e1", "checked", content_sha256="aaa")
            with self.assertRaises(state.TransitionError):
                state.transition(db, "e1", "site_live")            # skipping archive/commit
            state.transition(db, "e1", "archived")
            with self.assertRaises(state.TransitionError):
                state.transition(db, "e1", "site_committed", content_sha256="bbb")   # body changed without new revision
            state.transition(db, "e1", "site_committed", content_sha256="aaa")

    def test_runtime_env_outside_repo_and_no_values_in_describe(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "runtime.env"; p.write_text("EMAIL_RECIPIENTS=a@example.invalid,b@example.invalid\nSMTP_PASSWORD=s3cret\nEMAIL_SEND_ENABLED=false\n")
            p.chmod(0o644); rt = config.load_runtime(p)
            self.assertTrue(rt.insecure_permissions)
            d = json.dumps(rt.describe())
            self.assertNotIn("s3cret", d); self.assertNotIn("example.invalid", d)
            self.assertFalse(rt.send_enabled)



class RenderInventory(unittest.TestCase):
    def test_unscheduled_article_renders_but_stays_out_of_public_index(self):
        o = json.loads((ROOT / "samples/B/article.json").read_text()); o.update(edition_id="inv-1", edition_date="unscheduled")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td); render.build([dict(OBJ), o], out, "https://starhub.vip")
            self.assertTrue((out / "email/inv-1.html").exists())
            self.assertTrue((out / "site/data/history/unscheduled/inv-1.json").exists())
            ids = [i["edition_id"] for i in json.loads((out / "site/data/history/index.json").read_text())["items"]]
            self.assertEqual(ids, [OBJ["edition_id"]])

if __name__ == "__main__":
    unittest.main()

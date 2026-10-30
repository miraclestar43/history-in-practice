import json, os, subprocess, sys, tempfile, unittest
from email import message_from_bytes
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import smtp_fixture
ROOT = Path(__file__).resolve().parents[1]
ART = str(ROOT / "samples/D/article.json")


class CliSend(unittest.TestCase):
    """The documented first-test steps, run through the real CLI against a local SMTPS server."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); self.srv = smtp_fixture.start(tls=True)

    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close(); self.td.cleanup()

    def hip(self, *args, **env_overrides):
        env_file = Path(self.td.name) / "runtime.env"
        vals = {"SMTP_HOST": "127.0.0.1", "SMTP_PORT": str(self.srv.server_address[1]), "SMTP_SECURITY": "ssl", "SMTP_TLS_INSECURE_LOCAL": "true",
                "SMTP_USERNAME": "u", "SMTP_PASSWORD": "p", "EMAIL_FROM": "每日一鉴 <history@read.starhub.vip>",
                "EMAIL_REPLY_TO": "feedback@example.com", "EMAIL_RECIPIENTS": "r1@example.com,r2@example.com", "EMAIL_SEND_ENABLED": "false"}
        vals.update(env_overrides)
        env_file.write_text("".join(f"{k}={v}\n" for k, v in vals.items())); env_file.chmod(0o600)
        r = subprocess.run([str(ROOT / "bin/hip"), *args], capture_output=True, text=True,
                           env=dict(os.environ, HIP_DATA_DIR=str(Path(self.td.name) / "data"), HIP_RUNTIME_ENV=str(env_file)))
        try:
            return r.returncode, json.loads(r.stdout) if r.stdout.strip() else {}, r.stderr
        except ValueError:
            return r.returncode, {}, r.stdout + r.stderr

    def test_production_send_refuses_while_disabled(self):
        rc, out, _ = self.hip("send", ART, "--real")
        self.assertEqual(rc, 2); self.assertFalse(out["sent"]); self.assertIn("EMAIL_SEND_ENABLED", out["reason"])
        self.assertEqual(len(self.srv.messages), 0)

    def test_one_off_test_needs_confirmation_and_complete_config(self):
        rc, out, err = self.hip("send-test", ART); self.assertNotEqual(rc, 0); self.assertIn("--confirm-real-email", err)
        rc, out, _ = self.hip("send-test", ART, "--confirm-real-email", EMAIL_REPLY_TO="")
        self.assertEqual(rc, 2); self.assertIn("EMAIL_REPLY_TO", out["reason"]); self.assertEqual(len(self.srv.messages), 0)
        rc, out, _ = self.hip("send-test", ART, "--confirm-real-email", EMAIL_RECIPIENTS="")
        self.assertEqual(rc, 2); self.assertIn("empty", out["reason"])
        rc, out, _ = self.hip("send-test", ART, "--confirm-real-email")
        self.assertEqual(rc, 0, out); self.assertTrue(out["all_accepted"]); self.assertTrue(out["test_edition"].startswith("sample-D-test-"))
        self.assertEqual(len(self.srv.messages), 2)
        m = message_from_bytes(self.srv.messages[0][1])
        self.assertEqual(m["Reply-To"], "feedback@example.com"); self.assertIn("-test-", m["X-HIP-Edition"])
        self.assertNotIn("example.com", json.dumps(out).replace("feedback@example.com", ""))          # no addresses in the report


if __name__ == "__main__":
    unittest.main()

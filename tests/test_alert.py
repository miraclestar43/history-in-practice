"""Launch 2026-11-01: maintainer alerts (alert.py). A skipped/overdue/partial day, Claude unavailable, or low inventory ->
one email to the maintainer (ALERT_EMAIL, else Reply-To), never to subscribers, once per problem per LA day; an ordinary
wait while a deploy lands is not alerted."""
import os, sys, tempfile, unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import alert, config

LA = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 11, 2, 7, 35, tzinfo=LA)
RT = config.Runtime({"EMAIL_FROM": "没事儿多读书 <history@read.starhub.vip>", "EMAIL_REPLY_TO": "owner@example.invalid",
                     "EMAIL_RECIPIENTS": "reader@example.invalid", "SMTP_HOST": "smtp.example.invalid"}, None)


class Alert(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); os.environ["HIP_DATA_DIR"] = self.td.name
        self.sent = []

    def tearDown(self):
        os.environ.pop("HIP_DATA_DIR"); self.td.cleanup()

    def fake(self, cfg, msg, rcpt, timeout=30):
        self.sent.append((rcpt, str(msg["Subject"]), msg.get_content())); return "accepted", "250"

    def test_skipped_day_alerts_the_maintainer_once(self):
        alert.record("publish_last.json", {"date": "2026-11-02", "outcome": "skipped", "reason": "no eligible edition"})
        r = alert.run(RT, NOW, source="send", send_one=self.fake)
        self.assertEqual(r["alert"], "accepted"); self.assertEqual(self.sent[0][0], "owner@example.invalid")   # never a subscriber
        self.assertIn("无合格稿件", self.sent[0][2])
        self.assertEqual(alert.run(RT, NOW, source="send-retry", send_one=self.fake)["alert"], "already sent today")
        self.assertEqual(len(self.sent), 1)

    def test_ordinary_wait_is_quiet_but_waiting_near_the_deadline_alerts(self):
        alert.record("publish_last.json", {"date": "2026-11-02", "outcome": "waiting", "reason": "deploy not live yet"})
        self.assertEqual(alert.run(RT, NOW, source="send", deadline_s_left=3 * 3600, send_one=self.fake)["alert"], "none")
        self.assertEqual(alert.run(RT, NOW, source="send", deadline_s_left=20 * 60, send_one=self.fake)["alert"], "accepted")

    def test_claude_unavailable_and_low_inventory(self):
        import time
        alert.record("final_editor.json", {"final_editor": "unavailable", "problems": ["not logged in"], "checked_at": time.time(), "warnings": []})
        alert.record("nightly_last.json", {"writer_unavailable": "writer unavailable (Claude): not logged in", "inventory_alert": True,
                                           "coverage_days": 5})
        ps = alert.run(RT, NOW, source="prepare", dry_run=True)["problems"]
        self.assertTrue(any("不会改用其他模型" in p for p in ps)); self.assertTrue(any("5 天" in p for p in ps))

    def test_explicit_alert_address_wins(self):
        rt = config.Runtime(dict(RT.values, ALERT_EMAIL="ops@example.invalid"), None)
        alert.record("publish_last.json", {"date": "2026-11-02", "outcome": "overdue", "reason": "x"})
        alert.run(rt, NOW, source="send", send_one=self.fake)
        self.assertEqual(self.sent[0][0], "ops@example.invalid")


if __name__ == "__main__":
    unittest.main()

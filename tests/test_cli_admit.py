import json, os, subprocess, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def hip(*args, data):
    r = subprocess.run([str(ROOT / "bin/hip"), *args], capture_output=True, text=True, env=dict(os.environ, HIP_DATA_DIR=data))
    return r.returncode, json.loads(r.stdout) if r.stdout.strip() else {}


class Admit(unittest.TestCase):
    def test_new_article_only_as_sample_and_sample_needs_approval(self):
        with tempfile.TemporaryDirectory() as td:
            art, ev = str(ROOT / "samples/D/article.json"), str(ROOT / "samples/evidence_D.json")
            rc, out = hip("admit", art, ev, data=td); self.assertEqual(rc, 1); self.assertIn("pipeline", out["reason"])
            rc, out = hip("admit", art, ev, "--as-sample", data=td); self.assertEqual(rc, 0); self.assertFalse(out["schedulable"])
            rc, out = hip("admit", art, ev, "--as-sample", data=td); self.assertFalse(out["admitted"]); self.assertIn("already known", out["reason"])
            o = json.loads(Path(art).read_text()); o["edition_id"] = "copy-of-D"; o["episode_id"] = None; o["title"]["zh"] = "纽堡：另一个标题"
            p = Path(td) / "copy.json"; p.write_text(json.dumps(o, ensure_ascii=False))
            rc, out = hip("admit", str(p), ev, "--as-sample", data=td); self.assertEqual(rc, 1); self.assertIn("duplicate", out["reason"])
            rc, inv = hip("inventory", data=td)
            self.assertEqual((inv["schedulable_total"], inv["samples"]["total"], inv["samples"]["approved"]), (0, 1, 0))
            rc, out = hip("approve-sample", "sample-D", "--reason", "read and approved by both readers", data=td); self.assertEqual(rc, 0)
            rc, inv = hip("inventory", data=td)
            self.assertEqual((inv["schedulable_total"], inv["samples"]["approved"]), (1, 1))

    def test_pending_draft_needs_an_editor_record(self):
        with tempfile.TemporaryDirectory() as td:
            art, ev = str(ROOT / "samples/D/article.json"), str(ROOT / "samples/evidence_D.json")
            hip("admit", art, ev, "--as-sample", data=td)
            rc, out = hip("requeue", "sample-D", "--reason", "stricter review rule", data=td); self.assertEqual(rc, 0)
            rc, inv = hip("inventory", data=td); self.assertEqual(inv["pending"], 1)
            rc, out = hip("requeue", "sample-D", "--reason", "again", data=td); self.assertEqual(rc, 1)
            rc, out = hip("admit", art, ev, data=td); self.assertEqual(rc, 1); self.assertIn("--record", out["reason"])
            fake = Path(td) / "rec.json"; fake.write_text(json.dumps({"final_content_sha256": "0" * 64, "final_reviewed": True, "rounds": [{}]}))
            rc, out = hip("admit", art, ev, "--record", str(fake), "--exception", "trust me", data=td)
            self.assertEqual(rc, 1); self.assertIn("article content differs", " ".join(out["problems"]))     # exception cannot cover an unbound record
            rc, st = hip("status", data=td); self.assertEqual(st["recent"][0]["status"], "pending_review")


if __name__ == "__main__":
    unittest.main()

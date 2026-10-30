import json, os, subprocess, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def hip(*args, data):
    r = subprocess.run([str(ROOT / "bin/hip"), *args], capture_output=True, text=True, env=dict(os.environ, HIP_DATA_DIR=data))
    return r.returncode, json.loads(r.stdout) if r.stdout.strip() else {}


class Admit(unittest.TestCase):
    def test_admit_once_and_refuse_same_episode_under_new_id(self):
        with tempfile.TemporaryDirectory() as td:
            art, ev = str(ROOT / "samples/D/article.json"), str(ROOT / "samples/evidence_D.json")
            rc, out = hip("admit", art, ev, data=td); self.assertEqual(rc, 0); self.assertTrue(out["admitted"])
            rc, out = hip("admit", art, ev, data=td); self.assertFalse(out["admitted"]); self.assertIn("already known", out["reason"])
            o = json.loads(Path(art).read_text()); o["edition_id"] = "copy-of-D"; o["episode_id"] = None; o["title"]["zh"] = "纽堡：另一个标题"
            p = Path(td) / "copy.json"; p.write_text(json.dumps(o, ensure_ascii=False))
            rc, out = hip("admit", str(p), ev, data=td); self.assertEqual(rc, 1); self.assertIn("duplicate", out["reason"])
            rc, inv = hip("inventory", data=td); self.assertEqual(inv["days"], 1)


if __name__ == "__main__":
    unittest.main()

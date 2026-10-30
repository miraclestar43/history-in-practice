import copy, json, os, sys, tempfile, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import llm, checks

HERE = Path(__file__).parent; ROOT = HERE.parent
FAKE = str(HERE / "fake_hermes_runner.py")


def run(prompt, **kw):
    return llm.call(prompt, python=sys.executable, runner=FAKE, **kw)


class Runner(unittest.TestCase):
    """Mock runner: proves the caller's bounds. The real model path is measured in samples/model_timings*.json."""
    def test_valid_output(self):
        r = run("MODE=ok", timeout_s=30); self.assertEqual(r["rc"], 0); self.assertEqual(llm.parse_json(r["text"])["n"], 1)

    def test_error_exit_and_empty(self):
        self.assertEqual(run("MODE=err", timeout_s=30)["rc"], 4)
        r = run("MODE=empty", timeout_s=30); self.assertEqual(r["rc"], 3)
        with self.assertRaises(ValueError):
            llm.parse_json(r["text"])

    def test_timeout_kills_whole_process_tree(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["HIP_TEST_PIDFILE"] = str(Path(td) / "child.pid")
            t = time.monotonic(); r = run("MODE=hang", timeout_s=3)
            self.assertEqual(r["killed"], "timeout"); self.assertLess(time.monotonic() - t, 20)
            child = int(Path(os.environ["HIP_TEST_PIDFILE"]).read_text()); time.sleep(0.5)
            alive = True
            try:
                os.kill(child, 0)
                alive = Path(f"/proc/{child}/status").read_text().find("State:\tZ") < 0
            except ProcessLookupError:
                alive = False
            self.assertFalse(alive, "grandchild survived the timeout")

    def test_output_cap_enforced_while_running(self):
        t = time.monotonic(); r = run("MODE=flood", timeout_s=60)
        self.assertEqual(r["killed"], "stdout_cap"); self.assertLessEqual(r["out_bytes"], llm.MAX_STDOUT)
        self.assertLess(time.monotonic() - t, 20)


class ParseJSON(unittest.TestCase):
    def test_trailing_comma_slip_is_repaired_but_garbage_is_not(self):
        self.assertEqual(llm.parse_json('noise {"a": [1, 2, ], "b": {"c": 1, }, } tail')["a"], [1, 2])
        with self.assertRaises(ValueError):
            llm.parse_json("no json here")


class Checker(unittest.TestCase):
    def setUp(self):
        self.o = json.loads((ROOT / "samples/C/article.json").read_text())
        self.ev = json.loads((ROOT / "samples/evidence_C.json").read_text())

    def test_sample_passes(self):
        f, _ = checks.check(self.o, self.ev); self.assertFalse(checks.blocked(f), f)

    def test_record_paragraph_without_evidence_blocks(self):
        o = copy.deepcopy(self.o); o["sections"][2]["paras"][0]["ev"] = []
        self.assertTrue(checks.blocked(checks.check(o, self.ev)[0]))

    def test_unknown_evidence_id_blocks(self):
        o = copy.deepcopy(self.o); o["sections"][2]["paras"][0]["ev"] = ["C-E999"]
        self.assertTrue(checks.blocked(checks.check(o, self.ev)[0]))

    def test_invented_english_quote_blocks(self):
        o = copy.deepcopy(self.o); p = o["sections"][2]["paras"][1]
        p["en"] += ' Yung wrote that Woo "had never once visited a single school in New England".'
        f, _ = checks.check(o, self.ev); self.assertTrue(checks.blocked(f)); self.assertTrue(any("not verbatim" in m for _, m in f))

    def test_today_scene_repeating_the_question_is_flagged(self):
        o = copy.deepcopy(self.o); today = [s for s in o["sections"] if s["id"] == "today"][0]
        today["paras"][0]["zh"] = o["reflection"]["scenario"]["zh"]
        f, _ = checks.check(o, self.ev); self.assertTrue(any("repeat the open-question" in m for _, m in f))

    def test_number_drift_flagged(self):
        o = copy.deepcopy(self.o); p = o["sections"][1]["paras"][0]
        p["en"] = p["en"].replace("120", "102")
        f, _ = checks.check(o, self.ev); self.assertTrue(any("numbers differ" in m for _, m in f))


if __name__ == "__main__":
    unittest.main()

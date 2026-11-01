import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import state, pipeline


class Inventory(unittest.TestCase):
    """Coverage = days the editorial mix (mix.py: ~4 China / 3 elsewhere per 7, soft) can fill with approved editions."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); os.environ["HIP_DATA_DIR"] = self.td.name
        self.db = state.connect(Path(self.td.name) / "s.sqlite"); self.n = 0

    def tearDown(self):
        self.td.cleanup(); os.environ.pop("HIP_DATA_DIR")

    def add(self, cat, k=1, status="checked", approval="editor-record", origin="pipeline", date=None):
        for _ in range(k):
            self.n += 1; eid = f"e{self.n}"
            state.transition(self.db, eid, "prepared", category=cat)
            if status == "pending_review":
                state.transition(self.db, eid, "pending_review"); continue
            state.transition(self.db, eid, "checked", approval=approval, origin=origin)
            if status == "scheduled":
                state.transition(self.db, eid, "scheduled", edition_date=date)

    def inv(self):
        return pipeline.inventory(self.db, today="2026-11-01")

    def test_china_led_mix_four_of_seven_and_gaps_follow_the_plan(self):
        self.add("china_ancient", 3); self.add("world", 4); self.add("china_modern", 2); self.add("us", 3)
        i = self.inv(); seq = i["coverage_sequence"]
        self.assertEqual(i["schedulable_total"], 12)
        self.assertEqual(i["mix"]["china_in_next_7"], 4)                                         # ~4 China / 3 elsewhere
        self.assertEqual(seq[:7], ["china_ancient", "world", "china_modern", "us", "china_ancient", "world", "china_modern"])
        # 5 China, 7 other: once China runs out, "elsewhere" stands in only while every window of 7 keeps >= 3 China
        self.assertEqual(i["coverage_days"], 11)
        self.assertEqual(i["gaps_to_target"], {"china_ancient": 1, "china_modern": 2})            # 14 days want 8 China: A4 M4, W4 U2

    def test_scheduled_ahead_and_position(self):
        self.add("china_ancient", 3); self.add("world", 4); self.add("china_modern", 2); self.add("us", 3)
        self.add("china_ancient", 1, status="scheduled", date="2026-11-02")      # position 1 next -> an "other" slot
        i = self.inv()
        self.assertEqual(i["mix"]["next_position"], 1); self.assertEqual(i["scheduled_ahead"], 1)
        self.assertIn(i["next_category"], ("world", "us"))
        self.add("us", 1, status="scheduled", date="2026-10-20")                 # in the past: not counted as ahead
        self.assertEqual(self.inv()["scheduled_ahead"], 1)

    def test_samples_pending_and_unapproved_do_not_count(self):
        self.add("china_ancient", 1)
        self.add("world", 2, approval=None, origin="sample")                     # samples not yet approved
        self.add("world", 1, approval="sample-approved: read by both readers", origin="sample")
        self.add("china_modern", 2, status="pending_review")
        self.add("us", 1, approval=None)                                         # admitted before approvals were recorded
        i = self.inv()
        self.assertEqual(i["schedulable_by_category"], {"china_ancient": 1, "world": 1, "china_modern": 0, "us": 0})
        self.assertEqual(i["samples"], {"total": 3, "approved": 1}); self.assertEqual(i["pending"], 2)
        self.assertEqual(i["awaiting_approval_by_category"], {"world": 2, "us": 1})
        self.assertEqual(i["coverage_days"], 2); self.assertTrue(i["alert"])          # A then W
        self.assertIn("china_modern", i["missing_categories"])

    def test_empty_inventory(self):
        i = self.inv()
        self.assertEqual(i["coverage_days"], 0); self.assertTrue(i["alert"]); self.assertEqual(sum(i["gaps_to_target"].values()), 14)


class Mix(unittest.TestCase):
    """mix.plan: deterministic, ~4/7 China, alternates ancient/modern, varies themes/regions, bounded substitution."""
    def items(self, spec):
        from history_in_practice import mix
        return [mix.item(f"{c}-{k}", c, {"tags": tags, "title": {"zh": f"{c}-{k}"}}, k) for k, (c, tags) in enumerate(spec)]

    def test_pattern_alternation_and_variation(self):
        from history_in_practice import mix
        pool = self.items([("china_ancient", ["战争与冲突"]), ("china_ancient", ["经济与金融"]), ("china_modern", ["教育"]),
                           ("china_modern", ["外交"]), ("world", ["科学与技术"]), ("world", ["政治与治理"]), ("us", ["企业与商业"])])
        seq = mix.plan(pool, 7, 0)
        self.assertEqual([x["group"] for x in seq], ["china", "other"] * 3 + ["china"])
        cats = [x["category"] for x in seq if x["group"] == "china"]
        self.assertEqual(cats, ["china_ancient", "china_modern", "china_ancient", "china_modern"])   # ancient/modern alternate
        self.assertEqual(seq, mix.plan(list(reversed(pool)), 7, 0))                                  # deterministic
        self.assertTrue(all(x["reason"] for x in seq))

    def test_substitution_keeps_china_within_band_then_stops(self):
        from history_in_practice import mix
        seq = mix.plan(self.items([("world", [])] * 10), 10, 0)
        self.assertEqual(len(seq), 4)                     # at most 4 elsewhere in any 7 (China >= 3)
        self.assertTrue(seq[0]["reason"].startswith("替补"))
        seq = mix.plan(self.items([("china_modern", [])] * 10), 10, 0)
        self.assertEqual(len(seq), 5)                     # at most 5 China in any 7

    def test_persisted_plan_is_reused(self):
        from history_in_practice import mix
        db = state.connect(Path(tempfile.mkdtemp()) / "p.sqlite")
        seq = mix.plan(self.items([("china_ancient", []), ("world", [])]), 2, 0)
        mix.persist(db, 0, seq, "t"); self.assertEqual([x["edition_id"] for x in mix.stored(db, 0)], [x["edition_id"] for x in seq])
        mix.mark_used(db, 0, seq[0]["edition_id"]); self.assertEqual(mix.stored(db, 0)[0]["status"], "used")
        mix.persist(db, 0, [], "re-plan"); self.assertEqual([x["status"] for x in mix.stored(db, 0)], ["used"])   # used rows are history

if __name__ == "__main__":
    unittest.main()

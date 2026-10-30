import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import state, pipeline


class Inventory(unittest.TestCase):
    """Coverage = consecutive days the rotation (A, W, M, U) can fill from next_category with approved editions."""

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

    def test_reported_twelve_articles_cover_only_ten_days(self):
        self.add("china_ancient", 3); self.add("world", 4); self.add("china_modern", 2); self.add("us", 3)
        i = self.inv()
        self.assertEqual(i["schedulable_total"], 12); self.assertEqual(i["coverage_days"], 10)   # day 11 needs a third modern
        self.assertEqual(i["gaps_to_target"], {"china_ancient": 1, "china_modern": 1})           # A4/W4/M3/U3 for 14 days
        self.assertEqual(i["coverage_sequence"][:4], ["china_ancient", "world", "china_modern", "us"])

    def test_other_rotation_start_points(self):
        self.add("china_ancient", 3); self.add("world", 4); self.add("china_modern", 2); self.add("us", 3)
        self.add("china_ancient", 1, status="scheduled", date="2026-11-02")      # one already scheduled ahead -> next is world
        i = self.inv()
        self.assertEqual(i["next_category"], "world"); self.assertEqual(i["scheduled_ahead"], 1)
        # from W: W M U A W M U A W (9 days), then a 3rd modern is needed; plus the edition already scheduled ahead
        self.assertEqual(i["coverage_days"], 1 + 9)
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
        self.assertEqual(i["coverage_days"], 2); self.assertTrue(i["alert"])
        self.assertIn("china_modern", i["missing_categories"])

    def test_empty_inventory(self):
        i = self.inv()
        self.assertEqual(i["coverage_days"], 0); self.assertTrue(i["alert"]); self.assertEqual(sum(i["gaps_to_target"].values()), 14)


class Arithmetic(unittest.TestCase):
    """STABILIZATION_REVIEW §3: the report's what-if numbers come from the same function as `hip inventory`."""
    def test_review_scenarios(self):
        from history_in_practice.pipeline import rotation_days
        rot = ["china_ancient", "world", "china_modern", "us"]
        n = lambda a, w, m, u: dict(zip(rot, (a, w, m, u)))
        self.assertEqual(len(rotation_days(n(1, 2, 2, 1), rot, "china_ancient")), 4)     # report had said 2
        self.assertEqual(len(rotation_days(n(3, 4, 3, 3), rot, "china_ancient")), 12)    # report had said ~10
        self.assertEqual(len(rotation_days(n(3, 3, 3, 3), rot, "china_ancient")), 12)
        self.assertEqual(len(rotation_days(n(0, 1, 0, 0), rot, "china_ancient")), 0)
        self.assertEqual(rotation_days(n(1, 1, 0, 1), rot, "world"), ["world"])          # starts mid-rotation, stops at modern

if __name__ == "__main__":
    unittest.main()

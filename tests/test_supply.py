import json, os, shutil, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src")); sys.path.insert(0, str(Path(__file__).parent))
from history_in_practice import supply, evidence, registry, state, pipeline, editor
from test_registry_pipeline import ALIASES
ROOT = Path(__file__).resolve().parents[1]
ENTRY = {"id": "T56", "category": "china_ancient", "basis": "shiji", "cjk": True, "adapter": "wikisource_render", "ref": "zh:史記/卷056",
         "cache_id": "A-SJ56", "title": "史記·陳丞相世家（测试）", "must_contain": ["陳平"], "url": "https://example.invalid/sj56"}


def windows(text, n, start_at=200, step=260):
    """n non-overlapping anchors (start unique, end later in the same window) cut from the real fixture text."""
    out, i = [], start_at
    while len(out) < n and i + 80 < len(text):
        a = text[i:i + 12]
        if text.count(a) == 1:
            out.append({"id": f"E{len(out) + 1}", "label": f"段{len(out) + 1}", "start": a, "end": text[i + 60:i + 66]})
        i += step
    return out


class Supply(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); t = Path(self.td.name); os.environ["HIP_DATA_DIR"] = str(t / "data")
        self.cache = t / "cache"; self.cache.mkdir()
        shutil.copy(ROOT / "tests/fixtures/A-SJ56.txt", self.cache / "A-SJ56.txt")
        (self.cache / "A-SJ56.meta.json").write_text(json.dumps({"status": "evidence_usable", "source_id": "A-SJ56", "url": "https://example.invalid/sj56"}))
        self.db = state.connect(t / "s.sqlite"); registry.init(self.db, ALIASES)
        self.text = evidence.normalise((self.cache / "A-SJ56.txt").read_text(), True)
        self.out = t / "candidates"

    def tearDown(self):
        self.td.cleanup(); os.environ.pop("HIP_DATA_DIR")

    def model(self, excerpts, persons=("陈平",)):
        prop = {"title_hint": "陈平的六出奇计", "question_type": "相信谁",
                "episode": {"persons": list(persons), "year_from": -205, "year_to": -200, "place": "荥阳", "action": "陈平献计离间项羽君臣"},
                "excerpts": excerpts, "core": ["E2"], "brief": "类别：中国古代。有记录的骨架：陈平投汉 (E1)；献计 (E2)。", "preheader": {"zh": "z", "en": "e"}}
        def call(prompt, timeout_s=0, **kw):
            t = json.dumps(prop, ensure_ascii=False)
            return {"rc": 0, "killed": None, "wall_s": 0.1, "prompt_bytes": len(prompt), "prompt_chars": len(prompt), "out_bytes": len(t),
                    "out_chars": len(t), "stderr": "", "text": t}
        return call

    def propose(self, call):
        return supply.propose(ENTRY, self.db, call=call, cache=self.cache, date="20261030", out_dir=self.out)

    def test_anchors_are_verified_mechanically(self):
        good = windows(self.text, 14)
        bad = [{"id": "E90", "start": "這段話原文裡沒有出現過", "end": "沒有出現過"}, {"id": "E91", "start": "陳平", "end": "平"},
               {"id": "E92", "start": good[0]["start"], "end": good[0]["end"]}]                      # overlaps E1
        rec = self.propose(self.model(good + bad))
        self.assertEqual(rec["outcome"], "candidate", rec.get("reason")); self.assertEqual(rec["kept"], 14)
        reasons = {d["id"]: d["reason"] for d in rec["dropped"]}
        self.assertIn("occurs 0 times", reasons["E90"]); self.assertEqual(reasons["E91"], "anchor too short"); self.assertIn("overlaps", reasons["E92"])
        c = json.loads(Path(rec["path"]).read_text())
        self.assertEqual(c["core_excerpts"], ["T561-E2"]); self.assertIn("(T561-E1)", c["brief"]); self.assertIn("T561-E90", c["brief"])
        self.assertTrue(c["single_basis_disclosed"]); self.assertEqual(c["provenance"]["catalogue_id"], "T56")
        log = supply.attempts(); self.assertEqual(log[-1]["outcome"], "candidate")

    def test_too_few_valid_excerpts_or_lost_core_is_rejected_and_logged(self):
        rec = self.propose(self.model(windows(self.text, 8)))
        self.assertEqual(rec["outcome"], "rejected"); self.assertIn("only 8 valid excerpts", rec["reason"])
        ex = windows(self.text, 14); ex[1]["start"] = "不存在的開頭片段不存在的"
        rec = self.propose(self.model(ex)); self.assertIn("no core excerpt survived", rec["reason"])
        self.assertEqual([a["outcome"] for a in supply.attempts()], ["rejected", "rejected"]); self.assertFalse(self.out.exists() and list(self.out.iterdir()))

    def test_full_chain_with_fake_models_and_used_passages_are_not_reproposed(self):
        rec = self.propose(self.model(windows(self.text, 14)))
        c = pipeline.load_candidate(Path(rec["path"])); ids = [e[0] for e in c["excerpts"]]
        zh = {"title": "陈平", "dek": "d", "sections": [{"id": i, "heading": i, "paras": [{"t": "陈平投汉。", "kind": "record", "ev": [ids[0]]}]}
                                                       for i in ("hook", "context", "story", "analysis")] +
              [{"id": "today", "heading": "t", "paras": [{"t": "现代一", "kind": "modern", "ev": []}, {"t": "现代二", "kind": "modern", "ev": []}]},
               {"id": "limits", "heading": "l", "paras": [{"t": "只有一个史源。", "kind": "uncertainty", "ev": [ids[0]]}]}],
              "reflection": {"type": "相信谁", "scenario": "s", "question": "q", "example": {"assumptions": "a", "steps": "b", "alternative": "c"}},
              "uncertainty_note": "u"}
        en = json.loads(json.dumps(zh, ensure_ascii=False).replace("陈平投汉。", "Chen Ping joined Han.").replace("只有一个史源。", "One source only."))
        def call(prompt, timeout_s=0, **kw):
            out = ({"edits": [], "dispositions": []} if "事实编辑" in prompt else {"issues": [], "overall": "ok"}
                   if ("事实审稿人" in prompt or "English edition says the same" in prompt) else zh if "【编辑简报】" in prompt else en)
            t = json.dumps(out, ensure_ascii=False)
            return {"rc": 0, "killed": None, "wall_s": 0.1, "prompt_bytes": 1, "prompt_chars": 1, "out_bytes": len(t), "out_chars": len(t), "stderr": "", "text": t}
        wd = Path(self.td.name) / c["candidate_id"]
        r = pipeline.prepare(c, self.db, call=call, workdir=wd, cache=self.cache)
        self.assertEqual(r["outcome"], "pending_review", r.get("reason")); self.assertIn("awaiting editor stage", r["reason"])
        rec2 = editor.edit(wd, call=call); self.assertEqual(rec2["outcome"], "admissible", rec2["remaining"])
        self.assertTrue(editor.admit_with_record(self.db, wd / "edited.json", wd / "evidence.json", rec2)["admitted"])
        self.assertEqual(pipeline.inventory(self.db)["schedulable_by_category"]["china_ancient"], 1)
        again = self.propose(self.model(windows(self.text, 14)))                                       # the same passages again
        self.assertEqual(again["outcome"], "rejected")
        self.assertTrue(any("registered episode" in d["reason"] for d in again["dropped"]))


if __name__ == "__main__":
    unittest.main()

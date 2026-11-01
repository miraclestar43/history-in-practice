"""Book library -> nightly supply (2026-11-01). A real TXT book is ingested (acquired -> usable), cut into chapter units
(front matter left out), offered to the supply picker before the catalogue, and a model proposal from a unit becomes a
candidate whose excerpts carry their voice and book location; 【文学化】 passages are kept with their voice (2026-11-01); a unit with no complete
episode is skipped and logged; every attempt records which source it used. The model is a fake."""
import hashlib, json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import library, supply, state, registry, evidence

HAN = "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥天地玄黄宇宙洪荒日月盈昃辰宿列张寒来暑往秋收冬藏闰余成岁律吕调阳云腾致雨露结为霜"


def para(i: int) -> str:
    s = "".join(HAN[hashlib.sha256(f"{i}-{k}".encode()).digest()[0] % len(HAN)] for k in range(260))
    return f"知县某{i}号记：{s}。此事第{i}节终。"


class Library(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); root = Path(self.td.name)
        os.environ["HIP_DATA_DIR"] = str(root / "data")
        files = root / "data/books/files"; files.mkdir(parents=True)
        body = ["目录", "第一章 序言", "前言文字" * 300, "第二章 县衙里的一桩案子"] + [para(i) for i in range(30)] + \
               ["第三章 胡适的大方向"] + [para(100 + i) for i in range(12)] + ["第四章 收场"] + [para(200 + i) for i in range(25)]
        data = "\n\n".join(body).encode("utf-8")
        (files / "BK-T.txt").write_bytes(data)
        (root / "data/books/manifest.json").write_text(json.dumps({"files": [{"book_id": "BK-T", "path": "BK-T.txt", "format": "txt",
                                                                             "file_sha256": hashlib.sha256(data).hexdigest()}]}))
        self.old = library.LIB; library.LIB = root / "library.json"
        library.save({"books": [{"book_id": "BK-T", "title": "测试书", "author": "某人", "language": "zh", "genre": "scholarly_history",
                                 "categories": ["china_ancient"], "level": "acquired"}]})
        self.db = state.connect(root / "s.sqlite"); registry.init(self.db, {})
        self.out = root / "cands"

    def tearDown(self):
        library.LIB = self.old; os.environ.pop("HIP_DATA_DIR"); self.td.cleanup()

    def test_ingest_units_pick_propose_with_voices_and_locations(self):
        e = library.ingest("BK-T", verified="test")
        self.assertEqual(e["level"], "usable"); self.assertGreaterEqual(e["units"], 2)
        titles = [u["unit_title"] for u in library.entries()]
        self.assertFalse(any("序言" in t for t in titles))                     # front matter left out
        self.assertFalse(any("胡适" in t for t in titles))                     # paused people stay out of the pool
        pick = supply.pick_entry("china_ancient")
        self.assertEqual(pick["kind"], "book")                                 # books before the catalogue
        unit = evidence.normalise((Path(os.environ["HIP_DATA_DIR"]) / "source_cache/S-BK-T.txt").read_text(), True)[slice(*pick["offsets"])]
        paras = [p for p in unit.split("。此事第") if len(p) > 40][:14]
        exc = [{"id": f"E{k + 1}", "label": ("【文学化】想象" if k == 13 else "【作者】叙述"), "start": p[-60:-40], "end": p[-30:-20]}
               for k, p in enumerate(paras)]
        prop = {"title_hint": "一桩案子", "question_type": "如何纠错", "episode": {"persons": ["知县某"], "year_from": 1768, "year_to": 1768,
                "place": "某县", "action": "知县复核一桩案子"}, "excerpts": exc, "core": ["E1", "E12"], "tags": ["历史"],
                "brief": "类别：中国古代。(E1)", "preheader": {"zh": "z", "en": "e"}}
        seen = []
        def call(prompt, timeout_s=0, **kw):
            seen.append(prompt); return {"rc": 0, "killed": None, "wall_s": 0.1, "prompt_bytes": 1, "out_bytes": 1, "text": json.dumps(prop, ensure_ascii=False)}
        r = supply.propose(pick, self.db, call=call, out_dir=self.out)
        self.assertEqual(r["outcome"], "candidate", (r.get("reason"), r.get("dropped", [])[:3]))
        self.assertIn("【这段原文来自一本书】", seen[0]); self.assertIn("测试书", seen[0])
        self.assertFalse(any(d["id"] == "E14" for d in r["dropped"]), r["dropped"])  # a novelised telling is kept, labelled
        c = json.loads(Path(r["path"]).read_text())
        self.assertEqual(c["origin"], "book"); self.assertEqual(c["provenance"]["book"]["book_id"], "BK-T")
        locs = c["evidence_notes"]["excerpt_locations"]
        self.assertTrue(all("offset" in v["book_location"] for v in locs.values()))
        self.assertEqual(sorted(v["voice"] for v in locs.values()).count("【文学化】"), 1)
        self.assertTrue(all(v["voice"] in ("【作者】", "【文学化】") for v in locs.values()))
        log = supply.attempts()[-1]
        self.assertEqual((log["source_kind"], log["book_id"], log["unit"]), ("book", "BK-T", pick["unit"]))
        nxt = supply.pick_entry("china_ancient")                                # that unit is now tried: the next one is offered
        self.assertNotEqual(nxt["id"], pick["id"])

    def test_skip_and_missing_voice(self):
        library.ingest("BK-T", verified="test"); pick = supply.pick_entry("china_ancient")
        r = supply.propose(pick, self.db, call=lambda p, timeout_s=0, **k: {"rc": 0, "killed": None, "wall_s": 0, "prompt_bytes": 1, "out_bytes": 1,
                                                                         "text": '{"skip": "只有制度概论，没有完整事件"}'}, out_dir=self.out)
        self.assertEqual(r["outcome"], "rejected"); self.assertIn("no suitable episode", r["reason"])
        rows, dropped = supply.validate({"excerpts": [{"id": "E1", "label": "叙述", "start": "x" * 12, "end": "y" * 5}]}, "x" * 12 + "y" * 5, True,
                                        "S", "P", [], book=True)
        self.assertEqual(rows, []); self.assertIn("voice label", dropped[0]["reason"])

    def test_nightly_fill_tries_further_units_within_bounds(self):
        library.ingest("BK-T", verified="test")
        skip = lambda p, timeout_s=0, **k: {"rc": 0, "killed": None, "wall_s": 0, "prompt_bytes": 1, "out_bytes": 1, "text": '{"skip": "理论章节"}'}
        rs = supply.fill(["china_ancient"], self.db, tries_per_category=5, max_calls=2, call=skip)
        self.assertEqual(len(rs), 2)                                            # the night's call cap holds
        self.assertEqual(len({r["catalogue_id"] for r in rs}), 2)               # never the same unit twice
        self.assertTrue(all(r["source_kind"] == "book" and "no suitable episode" in r["reason"] for r in rs))

    def test_scanned_pdf_is_unsuitable(self):
        why = library.readability({"format": "pdf", "pdf_text_status": "needs_ocr", "paragraphs": []}, "zh")
        self.assertTrue(any("text layer" in w for w in why))


if __name__ == "__main__":
    unittest.main()

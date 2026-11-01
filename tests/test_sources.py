import http.server, json, sys, tempfile, threading, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import sources, evidence

PAGES = {
    "/challenge": (200, "text/html", "<html><title>Just a moment...</title>Checking the security of your connection</html>"),
    "/botwall": (202, "text/html", ""),
    "/missing": (404, "text/html", "<html>not found</html>"),
    "/home": (200, "text/html", "<html><title>StarHub | Command Center</title>home</html>"),
    "/irrelevant": (200, "text/html; charset=utf-8", "<html><body>项羽本纪 其他内容</body></html>"),
    "/good": (200, "text/html; charset=utf-8", "<html><body><p>漢王以爲然，乃出黃金四萬斤，與陳平，恣所爲，不問其出入。</p></body></html>"),
}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        st, ct, body = PAGES.get(self.path, (200, "text/html", PAGES["/home"][2]))   # unknown -> homepage (like starhub)
        b = body.encode(); self.send_response(st); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


class Classify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"; cls.td = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); cls.td.cleanup()

    def f(self, path, must=("四萬斤",), fallback=None):
        s = {"id": "T" + path.strip("/"), "adapter": "html", "ref": self.base + path, "must_contain": list(must)}
        if fallback: s["site_fallback_marker"] = fallback
        return sources.fetch(s, Path(self.td.name))

    def test_statuses(self):
        self.assertEqual(self.f("/challenge")["status"], "challenge_page")
        self.assertEqual(self.f("/botwall")["status"], "challenge_page")
        self.assertEqual(self.f("/missing")["status"], "wrong_url")
        self.assertEqual(self.f("/nope", fallback="StarHub | Command Center")["status"], "site_fallback")
        self.assertEqual(self.f("/irrelevant")["status"], "extractable")         # reachable, but not evidence
        r = self.f("/good"); self.assertEqual(r["status"], "evidence_usable"); self.assertEqual(len(r["text_sha256"]), 64)

    def test_excerpt_must_be_verbatim_and_source_usable(self):
        good = self.f("/good"); good.update(ref="zh:test", basis="b"); bad = self.f("/irrelevant"); bad.update(ref="zh:x", basis="b")
        pack, errs = evidence.build([["E1", "Tgood", "乃出黃金四萬斤", "不問其出入。", "loc"], ["E2", "Tirrelevant", "四萬斤", "。", "loc"],
                                     ["E3", "Tgood", "不存在", "。", "loc"]], {"Tgood": good, "Tirrelevant": bad}, Path(self.td.name))
        self.assertEqual([e["id"] for e in pack["excerpts"]], ["E1"])
        self.assertEqual(pack["excerpts"][0]["quote"], "乃出黃金四萬斤，與陳平，恣所爲，不問其出入。")
        self.assertTrue(any("E2" in e and "not evidence_usable" in e for e in errs)); self.assertTrue(any("E3" in e and "anchor" in e for e in errs))


if __name__ == "__main__":
    unittest.main()

"""Local preview server for screenshots (validation only, binds 127.0.0.1).
Serves the site dir, plus:
  /__harness?u=<path>&h=<px>  page with the real page in an iframe and a slow
                              image that holds the outer load event open, so
                              `firefox --screenshot` captures after JS fetches.
  /__delay                    sleeps then returns a 1x1 gif."""
import functools, http.server, sys, time, urllib.parse
GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == "/__delay":
            time.sleep(float(q.get("s", ["3"])[0]))
            self.send_response(200); self.send_header("Content-Type", "image/gif"); self.end_headers(); self.wfile.write(GIF); return
        if u.path == "/__harness":
            src = q["u"][0]; h = q.get("h", ["5200"])[0]
            body = (f'<!DOCTYPE html><html><body style="margin:0"><iframe src="{src}" style="border:0;width:100%;height:{h}px"></iframe>'
                    f'<img src="/__delay?s=3" width="1" height="1" alt=""></body></html>').encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(body); return
        if u.path.endswith(".json"):
            self.extensions_map[".json"] = "application/json"
        return super().do_GET()
if __name__ == "__main__":
    port, root = int(sys.argv[1]), sys.argv[2]
    http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=root)).serve_forever()

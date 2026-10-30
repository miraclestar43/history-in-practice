"""CLI-level local SMTP demo (no network). Fictional recipients only."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import smtp_fixture

srv = smtp_fixture.start(tls=True)
port = srv.server_address[1]
rcpts = ["ok@example.invalid", "refused@example.invalid", "dropped@example.invalid"]
srv.refuse_rcpt = {rcpts[1]}; srv.drop_in_data = {rcpts[2]}
with tempfile.TemporaryDirectory() as td:
    rf = Path(td) / "rcpts.txt"; rf.write_text("\n".join(rcpts))
    env = dict(os.environ, HIP_DATA_DIR=str(Path(td) / "data"))
    cmd = [str(ROOT / "bin/hip"), "send", str(ROOT / "samples/D/article.json"), "--local-smtp", f"127.0.0.1:{port}",
           "--security", "ssl", "--recipients-file", str(rf), "--out", str(Path(td) / "out")]
    for run in (1, 2):
        if run == 2:
            srv.refuse_rcpt = set(); srv.drop_in_data = set()
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        print(f"--- run {run} (exit {r.returncode})"); print(r.stdout.strip())
    st = subprocess.run([str(ROOT / "bin/hip"), "status"], capture_output=True, text=True, env=env).stdout
    print("--- status deliveries"); print(json.dumps(json.loads(st)["deliveries"], indent=1))
print("--- messages received by local server:", len(srv.messages), "sizes(bytes):", [len(b) for _, b in srv.messages])
srv.shutdown(); srv.server_close()

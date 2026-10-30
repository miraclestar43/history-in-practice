"""Hermes adapter: bounded caller for the project-level isolated runner
(hermes_isolated.py). Never uses `hermes -z` (see docs/reviews/OPUS_VALIDATION.md).
Bounded caller for hermes_isolated.py: process-group timeout, streaming
output caps (enforced while running, not after), wall-time + byte metrics."""
from __future__ import annotations
import json, os, signal, subprocess, tempfile, threading, time
from pathlib import Path

HERMES_PY = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/python")
RUNNER = str(Path(__file__).with_name("hermes_isolated.py"))
PROBE = None
MAX_STDOUT = 200_000   # bytes
MAX_STDERR = 8_000

def _pump(stream, buf: bytearray, cap: int, over: threading.Event):
    while True:
        chunk = stream.read(4096)
        if not chunk: break
        if len(buf) + len(chunk) > cap:
            buf.extend(chunk[: cap - len(buf)]); over.set(); break
        buf.extend(chunk)

def call(prompt: str, timeout_s: float = 900, model: str | None = None, python: str | None = None, runner: str | None = None) -> dict:
    data = prompt.encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="hip-hermes-") as wd:
        argv = [python or HERMES_PY, "-I", runner or RUNNER, wd] + (["--model", model] if model else [])
        t0 = time.monotonic()
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True, cwd=wd)
        out, err, over = bytearray(), bytearray(), threading.Event()
        th = [threading.Thread(target=_pump, args=(p.stdout, out, MAX_STDOUT, over), daemon=True),
              threading.Thread(target=_pump, args=(p.stderr, err, MAX_STDERR, threading.Event()), daemon=True)]
        for t in th: t.start()
        p.stdin.write(data); p.stdin.close()
        killed = None
        while p.poll() is None:
            if over.is_set(): killed = "stdout_cap"
            elif time.monotonic() - t0 > timeout_s: killed = "timeout"
            if killed:
                os.killpg(p.pid, signal.SIGTERM)
                try: p.wait(10)
                except subprocess.TimeoutExpired: os.killpg(p.pid, signal.SIGKILL); p.wait()
                break
            time.sleep(0.2)
        for t in th: t.join(5)
        wall = time.monotonic() - t0
    text = out.decode("utf-8", errors="replace")
    return {"rc": p.returncode, "killed": killed, "wall_s": round(wall, 1),
            "prompt_bytes": len(data), "prompt_chars": len(prompt),
            "out_bytes": len(out), "out_chars": len(text),
            "stderr": err.decode("utf-8", errors="replace")[-400:], "text": text}


def parse_json(text: str):
    import json
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1].rsplit("```", 1)[0]
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j < i:
        raise ValueError("no JSON object in model output")
    return json.loads(s[i:j + 1])

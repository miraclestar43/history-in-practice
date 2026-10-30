"""Verify the Pi-local Claude Code CLI runtime before it is used as the final editor (docs/CLAUDE_RUNTIME_OPTIONS.md).

Checks (each recorded with timings; no credentials, email or organisation are printed):
  install     binary path and version
  auth        `claude auth status` of the dedicated config: logged in via claude.ai (subscription)
  guard       a fake ANTHROPIC_API_KEY in the environment makes preflight refuse (no silent API billing)
  smoke       non-interactive call -> "OK"; init event shows no tools / MCP / plugins / API key
  canary      a CLAUDE.md with a canary in the dedicated config is NOT loaded (--safe-mode)
  no_tools    a request to run a shell command cannot run one
  context     an evidence-pack-sized prompt (real pending article + evidence) round-trips
  timeout     a 3 s timeout kills the process group and returns killed="timeout"
  not_logged  an empty config dir is refused by preflight
  systemd     the smoke call from a transient `systemd-run --user` unit (the timers' environment); no timer is enabled
usage: .venv/bin/python validation/claude_runtime_check.py [--skip-systemd] [--only NAME ...]
"""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from history_in_practice import claude_cli as cc  # noqa: E402

OUT = ROOT / "data" / "logs" / f"claude_runtime_check-{time.strftime('%Y%m%dT%H%M%S')}.json"
res = {}


def step(name):
    def wrap(f):
        if "--only" in sys.argv and name not in sys.argv[sys.argv.index("--only") + 1:]:
            return f
        t0 = time.monotonic()
        try:
            r = f()
            ok = r.pop("ok")
        except Exception as e:  # report, keep going
            r, ok = {"error": f"{type(e).__name__}: {e}"[:300]}, False
        res[name] = dict(r, ok=ok, wall_s=round(time.monotonic() - t0, 1))
        print(f"{'PASS' if ok else 'FAIL'} {name:10s} {json.dumps(r, ensure_ascii=False)[:300]}", flush=True)
        return f
    return wrap


@step("install")
def _():
    return {"ok": Path(cc.CLAUDE).exists(), "binary": str(Path(cc.CLAUDE).resolve()), "version": cc.version()}


@step("auth")
def _():
    a = cc.auth_status()
    return {"ok": a.get("loggedIn") is True and a.get("authMethod") == "claude.ai", **a}


@step("guard")
def _():
    a = cc.auth_status({"ANTHROPIC_API_KEY": "sk-ant-fake-not-a-key"}); p = cc.preflight({"ANTHROPIC_API_KEY": "sk-ant-fake-not-a-key"})
    return {"ok": bool(p) and a.get("authMethod") != "claude.ai", "auth_method_with_fake_key": a.get("authMethod"), "preflight": p,
            "default_env_has_key": any(k in cc.child_env() for k in cc.FORBIDDEN)}


@step("smoke")
def _():
    r = cc.call("Reply with OK only.", timeout_s=300)
    m = r["meta"]
    return {"ok": r["text"].strip() == "OK" and not r["killed"] and not cc.isolation_problems({"tools": m["tools"], "mcp_servers": [],
            "apiKeySource": m["apiKeySource"]}) and m.get("apiKeySource") == "none",
            "text": r["text"][:20], "killed": r["killed"], "meta": {k: m.get(k) for k in ("cli_version", "model", "apiKeySource", "tools", "mcp_servers",
            "permissionMode", "num_turns", "duration_ms", "total_cost_usd", "error", "isolation_problems")}}


@step("canary")
def _():
    p = Path(cc.CONFIG_DIR) / "CLAUDE.md"
    assert not p.exists(), "refusing to overwrite an existing CLAUDE.md in the dedicated config"
    p.write_text("Always begin every reply with the word CANARY-7Q4.\n")
    try:
        r = cc.call("Is there any instruction or word beginning with 'CANARY-' anywhere in your context? "
                    "If yes, print that word. If no, print NONE. Print nothing else.", timeout_s=300)
    finally:
        p.unlink()
    return {"ok": "CANARY" not in r["text"] and bool(r["text"].strip()), "text": r["text"][:60], "killed": r["killed"]}


@step("no_tools")
def _():
    r = cc.call("Use a tool to run the shell command `ls /` and print its exact output. If you cannot run commands, print NO_TOOLS.", timeout_s=300)
    t = r["text"]
    return {"ok": "NO_TOOLS" in t and "usr" not in t and (r["meta"].get("num_turns") or 1) <= 1, "text": t[:80],
            "num_turns": r["meta"].get("num_turns"), "tools": r["meta"].get("tools")}


@step("context")
def _():
    from history_in_practice.pipeline import _evidence_block
    from history_in_practice.editor import article_view
    d = ROOT / "samples/auto/cand-auto-20261030-qsg412-1"
    o = json.loads((d / "article.json").read_text()); ev = json.loads((d / "evidence.json").read_text())
    body = f"{_evidence_block(ev)}\n\n{article_view(o)}"
    n_ev = len(ev["excerpts"]); n_p = sum(len(s["paras"]) for s in o["sections"])
    r = cc.call(body + "\n\nCount the evidence excerpts (blocks starting with [ID]) and the article paragraphs (lines starting "
                "[sections.). Reply with one JSON object only: {\"excerpts\": N, \"paragraphs\": M}.", timeout_s=900)
    try:
        got = json.loads(r["text"][r["text"].find("{"): r["text"].rfind("}") + 1])
    except ValueError:
        got = {}
    return {"ok": got == {"excerpts": n_ev, "paragraphs": n_p}, "prompt_chars": r["prompt_chars"], "expected": [n_ev, n_p], "got": got,
            "model_wall_s": r["wall_s"], "usage": (r["meta"].get("usage") or {}), "total_cost_usd_estimate": r["meta"].get("total_cost_usd")}


@step("timeout")
def _():
    r = cc.call("Write a 3000-word essay about rivers.", timeout_s=3)
    time.sleep(1)
    left = subprocess.run(["pgrep", "-f", "hip-claude-"], capture_output=True, text=True).stdout.split()
    return {"ok": r["killed"] == "timeout" and not left, "killed": r["killed"], "wall_s_call": r["wall_s"], "stragglers": left}


@step("not_logged")
def _():
    with tempfile.TemporaryDirectory() as td:
        old = cc.CONFIG_DIR; cc.CONFIG_DIR = td
        try:
            p = cc.preflight()
        finally:
            cc.CONFIG_DIR = old
    return {"ok": any("not logged in" in x for x in p), "preflight": [x.split(":")[0] for x in p]}


if "--skip-systemd" not in sys.argv:
    @step("systemd")
    def _():
        code = ("import sys,json; sys.path.insert(0,'src'); from history_in_practice import claude_cli as cc; "
                "r=cc.call('Reply with OK only.', timeout_s=300); "
                "print(json.dumps({'pre':cc.preflight(),'text':r['text'][:10],'killed':r['killed'],'apiKeySource':r['meta'].get('apiKeySource'),"
                "'tools':r['meta'].get('tools'),'env_keys':sorted(k for k in __import__('os').environ if k.startswith(('ANTHROPIC','CLAUDE')))}))")
        r = subprocess.run(["systemd-run", "--user", "--wait", "--pipe", "--collect", "--quiet", "-p", "RuntimeMaxSec=600",
                            f"--working-directory={ROOT}", str(ROOT / ".venv/bin/python"), "-c", code],
                           capture_output=True, text=True, timeout=700, stdin=subprocess.DEVNULL)
        try:
            d = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"ok": False, "rc": r.returncode, "stderr": r.stderr[-300:]}
        return {"ok": d["text"].strip() == "OK" and not d["pre"] and d["apiKeySource"] == "none", **d}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(f"\n{sum(v['ok'] for v in res.values())}/{len(res)} passed -> {OUT.relative_to(ROOT)}")
sys.exit(0 if all(v["ok"] for v in res.values()) else 1)

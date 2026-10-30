"""Project-level isolated Hermes runner (validation; candidate for production).

Why: on the installed Hermes v0.14.0, `hermes -z PROMPT -t "" --ignore-rules`
does NOT isolate (verified 2026-10-30, see docs/reviews/OPUS_VALIDATION.md):
  * `-t ""` normalises to "no explicit toolsets" -> the configured CLI toolsets
    are enabled (29 tools incl. terminal, write_file, execute_code,
    send_message) and HERMES_YOLO_MODE=1 auto-approves them;
  * `--ignore-rules` only sets HERMES_IGNORE_RULES on the chat path; the -z
    dispatch happens earlier and AIAgent is built with skip_context_files=False,
    skip_memory=False, so SOUL.md, memory and cwd AGENTS.md are injected.

This runner is executed with Hermes's own venv python and builds AIAgent
directly with explicit isolation. It never prints or stores credentials; the
provider runtime is resolved inside the Hermes process exactly as `-z` does.

Contract: prompt on stdin (UTF-8, <= MAX_PROMPT_BYTES); response on stdout.
Exit codes: 0 ok, 2 bad input, 3 empty response (Hermes swallows provider
errors and returns "" with exit 0), 4 exception, 5 isolation assertion failed.
Usage: <hermes-venv-python> hermes_isolated.py <empty_workdir> [--model M]
"""
import contextlib, io, json, logging, os, sys

MAX_PROMPT_BYTES = 200_000
HERMES_SRC = os.path.expanduser("~/.hermes/hermes-agent")

def main() -> int:
    if len(sys.argv) < 2 or not os.path.isdir(sys.argv[1]) or os.listdir(sys.argv[1]):
        sys.stderr.write("usage: hermes_isolated.py <EMPTY_workdir> [--model M]\n"); return 2
    model_override = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else None
    raw = sys.stdin.buffer.read(MAX_PROMPT_BYTES + 1)
    if len(raw) > MAX_PROMPT_BYTES:
        sys.stderr.write("prompt too large\n"); return 2
    prompt = raw.decode("utf-8")
    os.chdir(sys.argv[1])
    for k in ("HERMES_YOLO_MODE", "HERMES_ACCEPT_HOOKS"):
        os.environ.pop(k, None)
    sys.path.insert(0, HERMES_SRC)
    logging.disable(logging.CRITICAL)
    real_stdout = sys.stdout
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            from hermes_cli.config import load_config
            from hermes_cli.runtime_provider import resolve_runtime_provider
            from run_agent import AIAgent
            cfg = load_config()
            m = cfg.get("model") or {}
            model = model_override or (m.get("default") if isinstance(m, dict) else m)
            rt = resolve_runtime_provider(requested=None, target_model=model)
            agent = AIAgent(api_key=rt.get("api_key"), base_url=rt.get("base_url"),
                            provider=rt.get("provider"), api_mode=rt.get("api_mode"),
                            model=model, enabled_toolsets=[], quiet_mode=True, platform="cli",
                            session_db=None, skip_context_files=True, skip_memory=True,
                            credential_pool=rt.get("credential_pool"))
            if agent.tools or not agent.skip_context_files or getattr(agent, "_memory_store", None):
                real_stdout.write(""); sys.__stderr__.write("isolation assertion failed\n"); return 5
            agent.suppress_status_output = True
            agent.stream_delta_callback = None
            agent.tool_gen_callback = None
            response = agent.chat(prompt) or ""
    except Exception as e:  # never echo provider internals
        sys.__stderr__.write(f"hermes_isolated: {type(e).__name__}\n"); return 4
    if not response.strip():
        sys.__stderr__.write("hermes_isolated: empty response\n"); return 3
    real_stdout.write(response); real_stdout.flush()
    sys.__stderr__.write(json.dumps({"model": model, "tools": 0}) + "\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())

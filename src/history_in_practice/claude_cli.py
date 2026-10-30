"""Pi-local official Claude Code CLI adapter (claude.ai subscription login, isolated, bounded).

Why a CLI adapter: the final editor runs on the Pi without depending on the Windows
VS Code session (see docs/CLAUDE_RUNTIME_OPTIONS.md). It calls the official
`claude` binary installed on the Pi (~/.local/bin/claude) with its own config
directory, logged in once by the owner with `claude auth login`.

Fail-closed rules:
* Subscription only. The child environment is built from an allowlist and never
  carries ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / CLAUDE_CODE_OAUTH_TOKEN or
  provider switches; `preflight()` refuses unless `claude auth status` reports
  authMethod "claude.ai". `--bare` is never used: it ignores the subscription
  login and would require an API key.
* Isolated. `--safe-mode` (no CLAUDE.md, memory, user skills/plugins, hooks, MCP),
  `--disable-slash-commands` (no bundled skills/commands), built-in plugins off in
  the dedicated settings.json (`enabledPlugins`), `--tools ""` (no tools at all, so the
  built-in agent types the CLI still lists cannot be invoked), `--disallowedTools mcp__*`,
  `--strict-mcp-config`, `--no-session-persistence`, an empty temporary working
  directory, a dedicated CLAUDE_CONFIG_DIR. The CLI's own `system/init` event is
  checked on every call: any tool, MCP server, plugin or API-key source -> the
  output is discarded (killed="isolation").
* Bounded. Process-group timeout, streaming stdout cap; authentication, rate-limit
  and other API errors are returned (never retried here) so callers can leave the
  item pending and alert.
Never logs credentials, email or organisation.
"""
from __future__ import annotations
import json, os, signal, subprocess, tempfile, threading, time
from pathlib import Path

CLAUDE = os.environ.get("HIP_CLAUDE_BIN", os.path.expanduser("~/.local/bin/claude"))
CONFIG_DIR = os.environ.get("HIP_CLAUDE_CONFIG_DIR", os.path.expanduser("~/.config/history-in-practice/claude"))
MODEL = os.environ.get("HIP_CLAUDE_MODEL", "claude-opus-5-5")
MAX_STDOUT = 4_000_000
ENV_ALLOW = ("HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR")
FORBIDDEN = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_PROFILE",
             "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")
SYSTEM = ("You are a careful text-processing assistant inside a batch job. You have no tools and no files: everything you need "
          "is in the user message. Follow its instructions exactly and reply with the requested output only.")


def child_env(extra: dict | None = None) -> dict:
    env = {k: os.environ[k] for k in ENV_ALLOW if k in os.environ}
    env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
    env.update(CLAUDE_CONFIG_DIR=CONFIG_DIR, DISABLE_AUTOUPDATER="1", DISABLE_TELEMETRY="1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
    env.update(extra or {})
    for k in FORBIDDEN:
        if k not in (extra or {}):
            env.pop(k, None)
    return env


def version() -> str:
    try:
        return subprocess.run([CLAUDE, "--version"], capture_output=True, text=True, timeout=30, env=child_env()).stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return f"unavailable ({type(e).__name__})"


def auth_status(extra_env: dict | None = None) -> dict:
    """Redacted `claude auth status`: no email, organisation or tokens."""
    try:
        r = subprocess.run([CLAUDE, "auth", "status"], capture_output=True, text=True, timeout=30, env=child_env(extra_env), cwd=tempfile.gettempdir())
        d = json.loads(r.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        return {"loggedIn": False, "authMethod": "unknown", "error": type(e).__name__}
    return {k: d.get(k) for k in ("loggedIn", "authMethod", "apiProvider", "subscriptionType", "configDirectory")}


def login_expiry() -> dict:
    """Days until the stored login's refresh token expires (timestamps only; never reads out a token)."""
    try:
        d = json.loads((Path(CONFIG_DIR) / ".credentials.json").read_text())["claudeAiOauth"]
    except (OSError, ValueError, KeyError):
        return {}
    r = d.get("refreshTokenExpiresAt")
    return {"access_expires_h": round((d.get("expiresAt", 0) / 1000 - time.time()) / 3600, 1),
            "refresh_expires_days": round((r / 1000 - time.time()) / 86400, 1) if r else None}


def warnings() -> list[str]:
    e = login_expiry().get("refresh_expires_days")
    return [f"Claude login for the final editor expires in {e} days: owner re-runs `claude auth login` with CLAUDE_CONFIG_DIR={CONFIG_DIR}"] \
        if e is not None and e < 7 else []


def preflight(extra_env: dict | None = None) -> list[str]:
    """Problems that must stop a final-editor run (empty = ready)."""
    if not Path(CLAUDE).exists():
        return [f"Claude Code CLI not installed at {CLAUDE}"]
    a = auth_status(extra_env); p = []
    if not a.get("loggedIn"):
        p.append(f"not logged in (config {CONFIG_DIR}): owner runs `CLAUDE_CONFIG_DIR={CONFIG_DIR} {CLAUDE} auth login`")
    elif a.get("authMethod") != "claude.ai":
        p.append(f"auth method is {a.get('authMethod')!r}, not the claude.ai subscription; refusing (no silent API billing)")
    return p


def _pump(stream, buf: bytearray, cap: int, over: threading.Event):
    while True:
        chunk = stream.read(65536)
        if not chunk:
            break
        if len(buf) + len(chunk) > cap:
            buf.extend(chunk[: cap - len(buf)]); over.set(); break
        buf.extend(chunk)


def isolation_problems(init: dict | None) -> list[str]:
    if not init:
        return ["no system/init event"]
    p = []
    if init.get("tools"):
        p.append(f"tools present: {init['tools'][:8]}")
    if init.get("mcp_servers"):
        p.append(f"MCP servers present: {[m.get('name') for m in init['mcp_servers']][:8]}")
    if init.get("plugins"):
        p.append(f"plugins present: {[x.get('name') for x in init['plugins']][:8]} (disable them in the dedicated settings.json enabledPlugins)")
    if init.get("skills") or init.get("slash_commands"):
        p.append(f"skills/commands present: {len(init.get('skills') or [])}/{len(init.get('slash_commands') or [])}")
    if init.get("apiKeySource") not in (None, "none"):
        p.append(f"apiKeySource is {init.get('apiKeySource')!r} (not the subscription login)")
    return p


def call(prompt: str, timeout_s: float = 1800, *, system: str = SYSTEM, model: str | None = None, effort: str | None = None,
         extra_env: dict | None = None) -> dict:
    """Same contract as llm.call (rc, killed, wall_s, text, byte counts) plus `meta` (init + result metadata, no secrets)."""
    data = prompt.encode("utf-8")
    argv = [CLAUDE, "-p", "--output-format", "stream-json", "--verbose", "--safe-mode", "--tools", "",
            "--disallowedTools", "mcp__*", "--strict-mcp-config", "--no-session-persistence", "--permission-prompts", "none", "--disable-slash-commands",
            "--setting-sources", "user", "--model", model or MODEL, "--system-prompt", system] + (["--effort", effort] if effort else [])
    with tempfile.TemporaryDirectory(prefix="hip-claude-") as wd:
        t0 = time.monotonic()
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True, cwd=wd, env=child_env(extra_env))
        out, err, over = bytearray(), bytearray(), threading.Event()
        th = [threading.Thread(target=_pump, args=(p.stdout, out, MAX_STDOUT, over), daemon=True),
              threading.Thread(target=_pump, args=(p.stderr, err, 16_000, threading.Event()), daemon=True)]
        for t in th:
            t.start()
        try:
            p.stdin.write(data); p.stdin.close()
        except BrokenPipeError:
            pass
        killed = None
        while p.poll() is None:
            if over.is_set():
                killed = "stdout_cap"
            elif time.monotonic() - t0 > timeout_s:
                killed = "timeout"
            if killed:
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(15)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL); p.wait()
                break
            time.sleep(0.2)
        for t in th:
            t.join(5)
        wall = time.monotonic() - t0
    init, result = None, None
    for line in out.decode("utf-8", errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            init = ev
        elif ev.get("type") == "result":
            result = ev
    meta = {"cli_version": (init or {}).get("claude_code_version"), "model": (init or {}).get("model"),
            "plugins": [x.get("name") for x in (init or {}).get("plugins") or []], "skills": len((init or {}).get("skills") or []),
            "apiKeySource": (init or {}).get("apiKeySource"), "tools": (init or {}).get("tools"),
            "mcp_servers": [m.get("name") for m in (init or {}).get("mcp_servers") or []],
            "permissionMode": (init or {}).get("permissionMode")}
    if result:
        meta.update({k: result.get(k) for k in ("subtype", "is_error", "num_turns", "duration_ms", "duration_api_ms", "total_cost_usd",
                                                 "usage", "modelUsage", "api_error_status", "stop_reason")})
    iso = isolation_problems(init)
    text = (result or {}).get("result") or ""
    if iso and not killed:
        killed, text = "isolation", ""                # never use output produced outside the isolated profile
        meta["isolation_problems"] = iso
    if result and result.get("is_error") and not killed:
        meta["error"] = str(result.get("result") or result.get("subtype"))[:300]; text = ""
    return {"rc": p.returncode, "killed": killed, "wall_s": round(wall, 1), "prompt_bytes": len(data), "prompt_chars": len(prompt),
            "out_bytes": len(out), "out_chars": len(text), "stderr": err.decode("utf-8", errors="replace")[-400:], "text": text,
            "meta": meta, "editor": {"name": "Pi Claude (Claude Code CLI)", "model": meta.get("model") or (model or MODEL),
                                     "cli_version": meta.get("cli_version")}}

"""Probe what `hermes -z` builds, without calling the model.
Mode 'cli': run the real hermes CLI entrypoint with given argv, AIAgent.chat patched.
Mode 'direct': build AIAgent with explicit isolation kwargs.
Prints only names/booleans/sizes; never prints prompt text or credentials."""
import json, os, sys, hashlib
sys.path.insert(0, os.path.expanduser("~/.hermes/hermes-agent"))
import run_agent
home = os.path.expanduser("~/.hermes")
soul = open(os.path.join(home, "SOUL.md"), encoding="utf-8").read().strip()
soul_probe = soul[:60] if soul else None

def summarize(agent):
    sp = agent._build_system_prompt()
    names = sorted(t["function"]["name"] for t in (agent.tools or []))
    return {
        "tool_count": len(names), "tools_sample": names[:40],
        "sys_prompt_chars": len(sp),
        "cwd_canary_in_prompt": "CANARY-CWD-AGENTS-7f3a" in sp,
        "soul_text_in_prompt": bool(soul_probe and soul_probe in sp),
        "memory_store_loaded": bool(getattr(agent, "_memory_store", None)),
        "memory_block_header_in_prompt": ("MEMORY" in sp) or ("memory" in sp.lower() and "<memory" in sp.lower()),
        "skip_context_files": agent.skip_context_files, "skip_memory": getattr(agent, "skip_memory", None),
        "env_HERMES_IGNORE_RULES": os.environ.get("HERMES_IGNORE_RULES"),
        "env_HERMES_YOLO_MODE": os.environ.get("HERMES_YOLO_MODE"),
    }

mode = sys.argv[1]
if mode == "cli":
    def fake_chat(self, prompt):
        return json.dumps(summarize(self), ensure_ascii=False)
    run_agent.AIAgent.chat = fake_chat
    from hermes_cli import main as hm
    sys.argv = ["hermes"] + sys.argv[2:]
    hm.main()
else:
    from hermes_cli.config import load_config
    from hermes_cli.runtime_provider import resolve_runtime_provider
    cfg = load_config(); m = cfg["model"]
    rt = resolve_runtime_provider(requested=None, target_model=m.get("default"))
    toolsets = json.loads(sys.argv[2])
    a = run_agent.AIAgent(api_key=rt.get("api_key"), base_url=rt.get("base_url"), provider=rt.get("provider"),
        api_mode=rt.get("api_mode"), model=m.get("default"), enabled_toolsets=toolsets, quiet_mode=True,
        platform="cli", session_db=None, skip_context_files=True, skip_memory=True)
    print(json.dumps(summarize(a), ensure_ascii=False))

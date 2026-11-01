"""The model that drafts, writes the English and edits (owner decision 2026-11-01): Claude Opus through the Pi's official
Claude Code CLI on the owner's claude.ai subscription (claude_cli: isolated, bounded, subscription-only, fail-closed).

Writing and reviewing stay separate calls with separate prompts and records (draft, review, English, edit rounds, final
audit/revise/verify, context review); only the model behind them is now the same.

MiMo through Hermes (llm.py, hermes_isolated.py) is kept for the record of earlier runs; nothing in the main chain calls
it, and there is no fallback to it. Hermes's own Anthropic credential is a pay-per-token API key ("claude_paid"), so it is
not used either (no paid API). If Claude is unavailable, preflight() says why and the job stops with a health failure
(nightly exit 4) and an alert; drafts stay where they are.
"""
from __future__ import annotations
from . import claude_cli

RUNTIME = "Claude Code CLI (claude.ai subscription)"


def call(prompt: str, timeout_s: float = 1800, **kw) -> dict:
    return claude_cli.call(prompt, timeout_s=timeout_s, **kw)


def preflight() -> list[str]:
    return claude_cli.preflight()


def label(metrics: list[dict]) -> dict:
    """Provider/model as the CLI reported them in its own init/result events (not a configured name)."""
    seen = [m.get("meta") or {} for m in metrics if (m.get("meta") or {}).get("model")]
    if not seen:
        return {"runtime": "unknown (no model reported by any call)", "model": None}
    used = sorted({k for s in seen for k in (s.get("modelUsage") or {})}) or sorted({s["model"] for s in seen})
    return {"runtime": RUNTIME, "model": seen[0]["model"], "models_used": used, "cli_version": seen[0].get("cli_version"),
            "api_key_source": seen[0].get("apiKeySource")}


def name(metrics: list[dict]) -> str:
    lb = label(metrics)
    return f"Claude ({lb['model']}) via {lb['runtime']}" if lb.get("model") else lb["runtime"]

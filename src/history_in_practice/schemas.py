"""Strict shapes for model outputs. A parseable JSON object is not a result: a review that lacks its
`issues` list, or carries mistyped entries, is a failed model step, never a clean review.

* ``review(obj)`` / ``parity(obj)`` / ``edit(obj)`` / ``draft_zh(obj)`` / ``draft_en(obj)`` return a list of
  problems (empty = valid). Problems never quote article text.
* The review prompt also asks for three separate fact arrays (unsupported_claims, invented_inner_life,
  quote_mismatches). ``fact_issues`` turns each entry into a fix-level issue so it cannot be silently ignored.
* ``REVIEW_SCHEMA`` / ``PARITY_SCHEMA`` are recorded with every bound review; a record whose final review was
  produced before validation existed is marked legacy and is re-validated on admission.
"""
from __future__ import annotations

REVIEW_SCHEMA = "review_zh/v2"           # v2: issues list required and typed; fact arrays folded into issues
PARITY_SCHEMA = "parity_en/v2"
FACT_ARRAYS = ("unsupported_claims", "invented_inner_life", "quote_mismatches")
REVIEW_SEVERITY = {"block", "fix", "note"}
PARITY_SEVERITY = {"fix", "note"}
PARA_KINDS = ("record", "interpretation", "modern", "uncertainty")


def _issue_list(obj, severities, where_keys) -> list[str]:
    p = []
    if not isinstance(obj, dict):
        return [f"not a JSON object ({type(obj).__name__})"]
    if "issues" not in obj:
        return ["missing required 'issues' list"]
    iss = obj["issues"]
    if not isinstance(iss, list):
        return [f"'issues' must be a list, got {type(iss).__name__}"]
    for k, i in enumerate(iss):
        if not isinstance(i, dict):
            p.append(f"issues[{k}] is not an object"); continue
        if i.get("severity") not in severities:
            p.append(f"issues[{k}].severity {i.get('severity')!r} not in {sorted(severities)}")
        if not isinstance(i.get("problem"), str) or not i["problem"].strip():
            p.append(f"issues[{k}].problem missing or not a string")
        for wk, types in where_keys.items():
            if wk in i and i[wk] is not None and not isinstance(i[wk], types):
                p.append(f"issues[{k}].{wk} has type {type(i[wk]).__name__}")
    return p


def review(obj) -> list[str]:
    p = _issue_list(obj, REVIEW_SEVERITY, {"section": (str,), "para": (int, str)})
    if p and p[0].startswith(("not a JSON", "missing required", "'issues' must")):
        return p
    for k in FACT_ARRAYS:
        if k in obj and obj[k] is not None:
            v = obj[k]
            if not isinstance(v, list):
                p.append(f"'{k}' must be a list, got {type(v).__name__}")
            elif any(not isinstance(x, (str, dict)) for x in v):
                p.append(f"'{k}' entries must be strings")
    return p


def parity(obj) -> list[str]:
    return _issue_list(obj, PARITY_SEVERITY, {"path": (str,)})


def edit(obj) -> list[str]:
    if not isinstance(obj, dict):
        return [f"not a JSON object ({type(obj).__name__})"]
    p = []
    if not isinstance(obj.get("dispositions"), list):
        p.append("missing required 'dispositions' list")
    for k in ("edits", "ev_changes"):
        if k in obj and obj[k] is not None and not isinstance(obj[k], list):
            p.append(f"'{k}' must be a list")
    for k, e in enumerate(obj.get("edits") or [] if isinstance(obj.get("edits"), list) else []):
        if not isinstance(e, dict) or not all(isinstance(e.get(x), str) for x in ("path", "find", "replace")):
            p.append(f"edits[{k}] needs string path/find/replace")
    for k, d in enumerate(obj.get("dispositions") or [] if isinstance(obj.get("dispositions"), list) else []):
        if not isinstance(d, dict) or d.get("action") not in ("fixed", "rejected") or not d.get("issue"):
            p.append(f"dispositions[{k}] needs issue and action fixed|rejected")
    return p


def _article_shape(obj, text_key) -> list[str]:
    if not isinstance(obj, dict):
        return [f"not a JSON object ({type(obj).__name__})"]
    p = [f"missing '{k}'" for k in ("title", "dek", "sections", "reflection", "uncertainty_note") if k not in obj]
    secs = obj.get("sections")
    if "sections" in obj and (not isinstance(secs, list) or not secs):
        p.append("'sections' must be a non-empty list")
    for k, s in enumerate(secs if isinstance(secs, list) else []):
        if not isinstance(s, dict) or "id" not in s or not isinstance(s.get("paras"), list):
            p.append(f"sections[{k}] needs id and a paras list"); continue
        for j, para in enumerate(s["paras"]):
            if not isinstance(para, dict) or text_key not in para:
                p.append(f"sections[{k}].paras[{j}] missing '{text_key}'")
    r = obj.get("reflection")
    if "reflection" in obj and (not isinstance(r, dict) or not isinstance(r.get("example"), dict)):
        p.append("'reflection' needs an 'example' object")
    return p


def draft_zh(obj) -> list[str]:
    p = _article_shape(obj, "t")
    for k, s in enumerate(obj.get("sections") or [] if isinstance(obj, dict) and isinstance(obj.get("sections"), list) else []):
        for j, para in enumerate(s.get("paras") or [] if isinstance(s, dict) else []):
            if isinstance(para, dict) and para.get("kind") not in PARA_KINDS:
                p.append(f"sections[{k}].paras[{j}].kind {para.get('kind')!r} unknown")
    return p


def draft_en(obj) -> list[str]:
    return _article_shape(obj, "t")


def fact_issues(obj) -> list[dict]:
    """Entries of the separate fact arrays, as review issues (severity fix, location unknown unless given)."""
    out = []
    for k in FACT_ARRAYS:
        for x in (obj or {}).get(k) or []:
            text = x if isinstance(x, str) else (x.get("problem") or x.get("text") or str(x))
            if str(text).strip():
                out.append({"severity": "fix", "kind": k, "problem": f"[{k}] {text}",
                            "section": x.get("section") if isinstance(x, dict) else None,
                            "para": x.get("para") if isinstance(x, dict) else None, "suggestion": ""})
    return out


def review_issues(obj) -> list[dict]:
    """All fix/block findings of a valid review: the typed issues list plus the separate fact arrays."""
    return [i for i in obj.get("issues", []) if i.get("severity") in ("fix", "block")] + fact_issues(obj)

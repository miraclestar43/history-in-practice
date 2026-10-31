"""Named final editor: Pi-local Claude Code CLI (claude_cli) closes drafts the MiMo editor stage could not.

Flow per edition (bounded; no MiMo rounds are added):
  audit    the final editor reads the whole article and the whole evidence pack, field by field
           (facts, attribution, chronology, causality, quotes, inner life, interpretation labels,
           EN/ZH parity), and judges every inherited MiMo issue (valid / invalid with evidence /
           duplicate) and every "contamination" line (brief lines that cited evidence later dropped).
  revise   every fix/block issue is fixed (full-field replacement, zh and en together) or rejected
           with a verbatim evidence quote. Deterministic checks decide whether a disposition counts:
           a fix needs a change citing it; a rejection needs a quote that really occurs in the cited
           excerpt. Anything else stays open.
  verify   a fresh field-by-field pass over the final text, bound to its content hash. New fix/block
           findings get one more revise/verify round (final_editor.max_rounds), then stay open.

The record (record_type "final_editor") binds: editor identity (name, model, CLI version, auth
method), base and final content hashes, evidence hash, the full edit log (replayable from the base
article), every issue with origin / disposition / rationale / evidence, the audit and verify coverage,
per-call timings and token use, and elapsed time. admit() re-checks all of it; there is no exception
path. A record never claims historical infallibility: sources stay linked and corrections stay possible.
"""
from __future__ import annotations
import copy, json, re, shutil, time
from pathlib import Path
from . import checks, render, state, registry, editor, schemas, claude_cli
from .config import REPO, data_dir, load_project
from .pipeline import PROMPTS, CODE_REV, _evidence_block
from .textnorm import t2s

RECORD_SCHEMA = "final-editor/v1"
CATEGORIES = {"facts", "attribution", "chronology", "causality", "quotes", "inner_life", "interpretation_label", "parity", "unsupported", "style"}
CHECKS = {"facts", "attribution", "chronology", "causality", "quotes", "inner_life", "interpretation_label", "parity"}
TIMEOUTS = {"audit": 1800, "revise": 1800, "verify": 1500}
MAX_ROUNDS = int(load_project().get("final_editor", {}).get("max_rounds", 2))
MAX_ATTEMPTS = int(load_project().get("final_editor", {}).get("max_attempts", 2))
# Runtime health failures (subscription limit, auth, CLI missing or killed by the runtime) are not editorial outcomes:
# they stop the queue, leave the edition pending and do not use up one of its MAX_ATTEMPTS.
HEALTH_MARKERS = ("usage limit", "rate limit", "rate_limit", "limit reached", "overloaded", "authentication", "not logged in",
                  "oauth", "api error", "api_error", "credit balance", "subscription", "not installed", "isolation")


def health_failure(text) -> bool:
    t = str(text or "").lower()
    return any(m in t for m in HEALTH_MARKERS)


def attempts_used(cid: str) -> int:
    """Final-editor attempts that count toward MAX_ATTEMPTS (runtime health failures excluded)."""
    root = data_dir() / "final_edit" / cid; n = 0
    for a in (root.glob("attempt-*") if root.exists() else []):
        r = a / "final_editor_record.json"
        if r.exists() and health_failure(json.loads(r.read_text(encoding="utf-8")).get("failure")):
            continue
        n += 1
    return n


OUT_ROOT = REPO / "samples/auto"            # git-tracked outputs (tests point this at a temp dir)
CANDIDATE_DIR = REPO / "config/candidates"
EDITOR = {"name": "Pi Claude", "role": "named final editor", "runtime": "official Claude Code CLI on raspberrypi51 (claude_cli.py)",
          "auth": "claude.ai subscription (dedicated config)"}


# ---------------------------------------------------------------- schemas (a parseable reply is not a result)

def _issue_problems(iss, prefix) -> list[str]:
    p = []
    if not isinstance(iss, list):
        return [f"'{prefix}' must be a list"]
    for k, i in enumerate(iss):
        if not isinstance(i, dict):
            p.append(f"{prefix}[{k}] not an object"); continue
        for f in ("id", "path", "problem"):
            if not isinstance(i.get(f), str) or not i[f].strip():
                p.append(f"{prefix}[{k}].{f} missing")
        if i.get("category") not in CATEGORIES:
            p.append(f"{prefix}[{k}].category {i.get('category')!r} unknown")
        if i.get("severity") not in ("block", "fix", "note"):
            p.append(f"{prefix}[{k}].severity {i.get('severity')!r} unknown")
        if i.get("severity") == "note" and i.get("category") != "style":
            p.append(f"{prefix}[{k}]: a {i.get('category')} issue cannot be a note")
        if not isinstance(i.get("evidence", []), list):
            p.append(f"{prefix}[{k}].evidence must be a list")
    return p


def _coverage_problems(obj, paths) -> list[str]:
    f = obj.get("fields")
    if not isinstance(f, list):
        return ["'fields' must be a list"]
    seen = {x.get("path") for x in f if isinstance(x, dict)}
    missing = [p for p in paths if p not in seen]
    p = [f"coverage misses {len(missing)} field(s): {missing[:5]}"] if missing else []
    thin = [x.get("path") for x in f if isinstance(x, dict) and x.get("path") in paths and not set(x.get("checked") or []) & CHECKS]
    if thin:
        p.append(f"fields with no checks recorded: {thin[:5]}")
    return p


def audit_schema(paths, inherited_ids):
    def v(obj):
        if not isinstance(obj, dict):
            return ["not a JSON object"]
        p = _coverage_problems(obj, paths) + _issue_problems(obj.get("issues"), "issues")
        inh = obj.get("inherited", [])
        if not isinstance(inh, list):
            return p + ["'inherited' must be a list"]
        got = {x.get("id") for x in inh if isinstance(x, dict)}
        if set(inherited_ids) - got:
            p.append(f"inherited issues without a verdict: {sorted(set(inherited_ids) - got)[:5]}")
        for x in inh:
            if isinstance(x, dict) and x.get("verdict") not in ("valid", "invalid", "duplicate"):
                p.append(f"inherited {x.get('id')}: verdict {x.get('verdict')!r}")
        return p
    return v


def verify_schema(paths):
    def v(obj):
        if not isinstance(obj, dict):
            return ["not a JSON object"]
        return _coverage_problems(obj, paths) + _issue_problems(obj.get("issues"), "issues")
    return v


def revise_schema(issue_ids):
    def v(obj):
        if not isinstance(obj, dict):
            return ["not a JSON object"]
        p = []
        if not isinstance(obj.get("changes"), list):
            p.append("'changes' must be a list")
        d = obj.get("dispositions")
        if not isinstance(d, list):
            return p + ["'dispositions' must be a list"]
        got = {x.get("issue") for x in d if isinstance(x, dict) and x.get("action") in ("fixed", "rejected")}
        if set(issue_ids) - got:
            p.append(f"issues without a disposition: {sorted(set(issue_ids) - got)[:5]}")
        return p
    return v


# ---------------------------------------------------------------- deterministic checks

def _norm(s: str) -> str:
    return re.sub(r"\s+", "", t2s(str(s)))


def quote_ok(ev: dict, cite: dict) -> bool:
    """A cited quote counts only if it occurs verbatim (whitespace and 繁简 normalised) in that excerpt."""
    e = next((x for x in ev["excerpts"] if x["id"] == cite.get("id")), None)
    q = _norm(cite.get("quote", ""))
    return bool(e) and len(q) >= 2 and (q in _norm(e.get("quote", "")) or q in _norm(e.get("display", "")))


def apply_changes(o: dict, ev: dict, changes: list) -> tuple[list, list]:
    """Full-field replacements of text (.zh/.en), ev lists and kinds. Returns (applied, failed)."""
    ev_ids = {e["id"] for e in ev["excerpts"]}; applied, failed = [], []
    for c in changes or []:
        try:
            path = c["path"]; r, k = editor.ref(o, path); before = r[k]
            if k in ("zh", "en"):
                new = c.get("text")
                if not isinstance(new, str) or not new.strip():
                    raise ValueError("text must be a non-empty string")
            elif k == "ev":
                new = list(c.get("value") or [])
                if not set(new) <= ev_ids:
                    raise ValueError(f"unknown evidence ids {sorted(set(new) - ev_ids)}")
            elif k == "kind":
                new = c.get("value")
                if new not in schemas.PARA_KINDS:
                    raise ValueError(f"unknown kind {new!r}")
            else:
                raise ValueError("only .zh, .en, .ev and .kind fields can change")
            if new == before:
                continue
            r[k] = new
            applied.append({"path": path, "before": before, "after": new, "issues": list(c.get("issues") or [])})
        except Exception as x:
            failed.append({"change": c, "error": f"{type(x).__name__}: {x}"})
    for s in o["sections"]:
        for i, p in enumerate(s["paras"]):
            if p["kind"] == "modern" and p["ev"]:
                failed.append({"change": {"path": f"sections.{s['id']}.{i}"}, "error": "modern paragraph cites evidence"})
    return applied, failed


def replay(base: dict, edits: list) -> dict:
    o = copy.deepcopy(base)
    for e in edits:
        r, k = editor.ref(o, e["path"])
        if r[k] != e["before"]:
            raise ValueError(f"edit log does not replay at {e['path']}")
        r[k] = e["after"]
    render.finalize(o)
    return o


def judge(issue_ids, dispositions, applied, ev) -> tuple[dict, list]:
    """Which dispositions count. fixed: a change cites the issue. rejected: a verified evidence quote."""
    cited = {i for e in applied for i in e["issues"]}
    out, open_ = {}, []
    disp = {d.get("issue"): d for d in dispositions or [] if isinstance(d, dict)}
    for iid in issue_ids:
        d = disp.get(iid) or {}
        if d.get("action") == "fixed" and iid in cited and str(d.get("rationale", "")).strip():
            out[iid] = {"disposition": "fixed", "rationale": d["rationale"]}
        elif d.get("action") == "rejected" and str(d.get("rationale", "")).strip() and d.get("evidence") and all(quote_ok(ev, c) for c in d["evidence"]):
            out[iid] = {"disposition": "rejected", "rationale": d["rationale"], "evidence": d["evidence"]}
        else:
            why = ("no disposition" if not d else "fixed without a change citing it" if d.get("action") == "fixed"
                   else "rejected without a verbatim evidence quote" if d.get("action") == "rejected" else f"action {d.get('action')!r}")
            open_.append({"issue": iid, "open_because": why, "claimed": d})
    return out, open_


# ---------------------------------------------------------------- inputs

def _latest_model_record(cid: str) -> Path | None:
    p = OUT_ROOT / cid / "editor_record.json"
    return p if p.exists() else None


def inherited_issues(cid: str, o: dict, ev: dict) -> list[dict]:
    """Open MiMo-stage issues: the record's `remaining` plus everything its final review raised (fact arrays included)."""
    rp = _latest_model_record(cid)
    if rp:
        rec = json.loads(rp.read_text(encoding="utf-8")); last = (rec.get("rounds") or [{}])[-1]
        rv, pv = editor.model_view(last.get("review_after")), editor.model_view(last.get("parity_after"))
        found = list(rec.get("remaining") or [])
    else:                                              # no editor stage yet: the pipeline's initial review
        dr = data_dir() / "drafts" / cid / "review_zh.json"
        rv, pv, found = (json.loads(dr.read_text(encoding="utf-8")) if dr.exists() else None), None, []
    if rv is not None and not schemas.review(rv):
        found += editor.collect_issues(rv, pv if pv is not None and not schemas.parity(pv) else None, [])
    out, seen = [], set()
    for i in found:
        key = str(i.get("problem"))
        if key in seen or i.get("source") == "checker":
            continue
        seen.add(key)
        out.append({"id": f"M{len(out) + 1}", "model_id": i.get("id"), "source": f"mimo-{i.get('source', 'review')}",
                    "where": i.get("where"), "problem": i.get("problem"), "suggestion": i.get("suggestion")})
    return out


def contamination(cid: str, ev: dict) -> list[dict]:
    """Brief lines that cite excerpts which did not survive into the evidence pack (supply drops them for new candidates)."""
    kept = {e["id"] for e in ev["excerpts"]}
    for p in CANDIDATE_DIR.glob("*.json"):
        c = json.loads(p.read_text(encoding="utf-8"))
        if c.get("candidate_id") != cid:
            continue
        out = []                                   # ids the brief cites that are not in the pack (the candidate file keeps only survivors)
        for line in str(c.get("brief", "")).splitlines():
            gone = sorted(set(re.findall(r"[A-Za-z0-9]+-E\d+", line)) - kept)
            if gone:
                out.append({"id": f"K{len(out) + 1}", "brief_line": line.strip(), "dropped_ids": gone})
        return out
    return []


def prior_final(cid: str) -> dict | None:
    """The previous final-editor attempt's record, if any: a later attempt continues from its text and open issues."""
    p = OUT_ROOT / cid / "final" / "final_editor_record.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def carried_issues(prior: dict, o: dict | None = None, ev: dict | None = None) -> list[dict]:
    """Open issues of the previous attempt. A checker-origin issue gets the current checker message at the same
    location on the text being edited (e.g. the specific shared phrases), so the editor sees what to change."""
    open_ids = set(prior.get("open_issues") or [])
    now = {}
    if o is not None and ev is not None:
        for lvl, m in checks.check(o, ev)[0]:
            if lvl in ("BLOCK", "FIX"):
                now.setdefault(m.split()[0], f"checker: {m}")
    out = []
    for k, i in enumerate(x for x in prior.get("issues") or [] if x["id"] in open_ids):
        prob = i.get("problem")
        if i.get("origin") == "checker":
            prob = now.get(str(prob).removeprefix("checker: ").split()[0], prob)
        out.append({"id": f"P{k + 1}", "model_id": i["id"], "source": "final-editor previous attempt", "where": i.get("path"),
                    "problem": prob, "suggestion": i.get("proposed")})
    return out


def base_paths(cid: str, db) -> tuple[Path, Path] | None:
    d = OUT_ROOT / cid
    if (d / "final" / "article.json").exists():           # continue from the previous final-editor attempt
        return d / "final" / "article.json", d / "final" / "evidence.json"
    if (d / "article.json").exists() and (d / "evidence.json").exists():
        return d / "article.json", d / "evidence.json"
    cur = state.get(db, cid)
    if cur and cur.get("path") and Path(cur["path"]).exists():
        art = Path(cur["path"]); evp = art.parent / "evidence.json"
        if not evp.exists():
            evp = REPO / "samples" / f"evidence_{art.parent.name}.json"
        return (art, evp) if evp.exists() else None
    return None


# ---------------------------------------------------------------- run

def _view(o, ev, extra: str = "") -> str:
    return f"【证据包】\n{_evidence_block(ev)}\n\n【稿件】\n{editor.article_view(o)}{extra}"


def run(cid: str, db, *, call=None, max_rounds: int = MAX_ROUNDS, operator_note: str | None = None) -> dict:
    """Final-edit one pending edition. Writes samples/auto/<cid>/final/ (git) and returns the record."""
    call = call or claude_cli.call
    if call is claude_cli.call:
        pre = claude_cli.preflight()
        if pre:
            return {"candidate_id": cid, "outcome": "not_run", "reason": "; ".join(pre)}
    src = base_paths(cid, db)
    if not src:
        return {"candidate_id": cid, "outcome": "not_run", "reason": "no article/evidence found"}
    root = data_dir() / "final_edit" / cid; n = len(list(root.glob("attempt-*"))) + 1 if root.exists() else 1
    w = root / f"attempt-{n}"; w.mkdir(parents=True, exist_ok=True)
    o = json.loads(src[0].read_text(encoding="utf-8")); ev = json.loads(src[1].read_text(encoding="utf-8"))
    render.finalize(o); base = copy.deepcopy(o)
    (w / "base_article.json").write_text(json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")
    (w / "evidence.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    paths = [p for p, _, _ in editor.fields(o)]
    prior = prior_final(cid)
    inh = carried_issues(prior, o, ev) if prior else inherited_issues(cid, o, ev)   # MiMo issues were all decided in the first attempt
    cont = contamination(cid, ev)
    t0 = time.time(); caller = editor.Caller(w, cid, call)
    rec = {"record_type": "final_editor", "schema": RECORD_SCHEMA, "candidate_id": cid, "edition_id": o["edition_id"],
           "editor": dict(EDITOR, model=claude_cli.MODEL, cli_version=claude_cli.version() if call is claude_cli.call else "test-double"),
           "code_rev": CODE_REV, "started_at": t0, "base_source": str(src[0].relative_to(REPO)) if src[0].is_relative_to(REPO) else str(src[0]),
           "base_content_sha256": base["content_sha256"], "evidence_sha256": editor.sha(ev), "operator_note": operator_note,
           "model_record_sha256": editor.sha(json.loads(_latest_model_record(cid).read_text())) if _latest_model_record(cid) else None,
           "prior_record_sha256": editor.sha(prior) if prior else None, "attempt": w.name,
           "inherited": inh, "contamination": cont, "issues": [], "edits": [], "rounds": []}
    ctx = (f"\n\n【遗留问题】\n{json.dumps(inh, ensure_ascii=False, indent=1)}\n\n【已知污染】\n{json.dumps(cont, ensure_ascii=False, indent=1)}"
           f"\n\n【必须覆盖的字段路径】\n{json.dumps(paths, ensure_ascii=False)}")
    audit = caller("audit", f"{(PROMPTS / 'final_audit.md').read_text()}\n\n{_view(o, ev, ctx)}", TIMEOUTS["audit"],
                   "\n\n[Reply with one valid JSON object only, matching the schema.]", validate=audit_schema(paths, [i["id"] for i in inh]))
    rec["audit"] = audit
    if audit is None:
        return _finish(rec, w, o, cid, caller, "audit failed: " + _why(caller))
    issues = {}
    for i in audit["issues"]:
        issues[i["id"]] = dict(i, origin="final-editor audit")
    for x in audit["inherited"]:
        m = next(i for i in inh if i["id"] == x["id"])
        if x["verdict"] == "valid":
            issues[m["id"]] = {"id": m["id"], "path": m.get("where") or "", "category": "unsupported", "severity": "fix",
                               "problem": m["problem"], "origin": f"inherited {m['source']} {m.get('model_id')}", "audit_rationale": x.get("rationale")}
        elif x["verdict"] == "invalid":   # still needs a verifiable evidence quote, else it stays an open issue
            ok = bool(x.get("evidence")) and all(quote_ok(ev, c) for c in x["evidence"])
            issues[m["id"]] = {"id": m["id"], "path": m.get("where") or "", "category": "unsupported", "severity": "fix", "problem": m["problem"],
                               "origin": f"inherited {m['source']} {m.get('model_id')}",
                               **({"disposition": "rejected", "rationale": x.get("rationale"), "evidence": x["evidence"], "decided_in": "audit"} if ok else
                                  {"audit_rationale": x.get("rationale"), "note": "audit called it invalid without a verifiable quote; must be handled"})}
        else:
            issues[m["id"]] = {"id": m["id"], "problem": m["problem"], "origin": f"inherited {m['source']} {m.get('model_id')}",
                               "severity": "fix", "category": "unsupported", "path": m.get("where") or "",
                               "disposition": "duplicate", "same_as": x.get("same_as"), "rationale": x.get("rationale")}
    for iid, i in issues.items():
        if i.get("disposition") == "duplicate" and i.get("same_as") not in issues:
            i.pop("disposition"); i["note"] = f"duplicate of unknown issue {i.get('same_as')!r}; handled on its own"
    open_ids = [k for k, i in issues.items() if i["severity"] in ("fix", "block") and "disposition" not in i]
    for rnd in range(1, max_rounds + 1):
        r = {"round": rnd, "issues_in": list(open_ids)}
        if open_ids:
            todo = [issues[k] for k in open_ids]
            rev = caller(f"revise_r{rnd}", f"{(PROMPTS / 'final_revise.md').read_text()}\n\n{_view(o, ev)}\n\n【问题清单】\n"
                         f"{json.dumps(todo, ensure_ascii=False, indent=1)}", TIMEOUTS["revise"],
                         "\n\n[Reply with one valid JSON object only, matching the schema.]", validate=revise_schema(open_ids))
            if rev is None:
                rec["rounds"].append(r); return _finish(rec, w, o, cid, caller, f"revise round {rnd} failed: " + _why(caller), issues)
            applied, failed = apply_changes(o, ev, rev["changes"])
            done, still = judge(open_ids, rev["dispositions"], applied, ev)
            for k, d in done.items():
                issues[k].update(d, decided_in=f"revise_r{rnd}")
            rec["edits"] += applied; render.finalize(o)
            r.update(changes_applied=len(applied), changes_failed=failed, still_open=still)
        findings, _ = checks.check(o, ev)
        ver = caller(f"verify_r{rnd}", f"{(PROMPTS / 'final_verify.md').read_text()}\n\n{_view(o, ev)}\n\n【必须覆盖的字段路径】\n{json.dumps(paths, ensure_ascii=False)}",
                     TIMEOUTS["verify"], "\n\n[Reply with one valid JSON object only, matching the schema.]", validate=verify_schema(paths))
        r.update(checker_after=findings, content_sha256_after=o["content_sha256"])
        if ver is None:
            rec["rounds"].append(r); return _finish(rec, w, o, cid, caller, f"verify round {rnd} failed: " + _why(caller), issues)
        ver["_content_sha256"] = o["content_sha256"]; r["verify"] = ver
        for i in ver["issues"]:
            if i["severity"] in ("fix", "block"):
                vid = f"V{rnd}-{i['id']}"; issues[vid] = dict(i, id=vid, origin=f"final-editor verify round {rnd}")
        for lvl, msg in findings:
            if lvl in ("BLOCK", "FIX"):
                cidk = f"C{rnd}-{len(issues) + 1}"; issues[cidk] = {"id": cidk, "path": "", "category": "unsupported", "severity": lvl.lower(),
                                                                     "problem": f"checker: {msg}", "origin": "checker"}
        rec["rounds"].append(r)
        open_ids = [k for k, i in issues.items() if i["severity"] in ("fix", "block") and "disposition" not in i]
        if not open_ids:
            break
    return _finish(rec, w, o, cid, caller, None, issues)


def _why(caller) -> str:
    m = caller.metrics[-1] if caller.metrics else {}
    return str(m.get("provider_refusal") or (m.get("meta") or {}).get("error") or m.get("schema_problems") or m.get("killed") or "no usable JSON")[:300]


def _finish(rec, w, o, cid, caller, failure, issues=None) -> dict:
    if issues is not None:
        rec["issues"] = list(issues.values())
    open_ = [i for i in rec["issues"] if i.get("severity") in ("fix", "block") and i.get("disposition") not in ("fixed", "rejected", "duplicate")]
    last = rec["rounds"][-1] if rec["rounds"] else {}
    bound = bool(last.get("verify")) and last["verify"].get("_content_sha256") == o["content_sha256"]
    rec.update(final_content_sha256=o["content_sha256"], open_issues=[i["id"] for i in open_],
               outcome="admissible" if not failure and bound and not open_ else "pending_review", failure=failure,
               finished_at=time.time(), calls=[{k: m.get(k) for k in ("step", "attempt", "wall_s", "json_ok", "schema_ok", "schema_problems", "killed")}
                                               | {"tokens": {k: ((m.get("meta") or {}).get("usage") or {}).get(k) for k in
                                                             ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")},
                                                  "cost_estimate_usd": (m.get("meta") or {}).get("total_cost_usd")} for m in caller.metrics])
    rec["elapsed_min"] = round((rec["finished_at"] - rec["started_at"]) / 60, 1)
    rec["model_wall_min"] = round(sum(m.get("wall_s", 0) for m in caller.metrics) / 60, 1)
    if caller.metrics and caller.metrics[-1].get("meta"):
        rec["editor"]["model_reported"] = caller.metrics[-1]["meta"].get("model")
    (w / "final_article.json").write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    (w / "final_editor_record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    out = OUT_ROOT / cid / "final"; out.mkdir(parents=True, exist_ok=True)
    shutil.copy(w / "final_article.json", out / "article.json"); shutil.copy(w / "evidence.json", out / "evidence.json")
    shutil.copy(w / "base_article.json", out / "base_article.json"); shutil.copy(w / "final_editor_record.json", out / "final_editor_record.json")
    shutil.copy(w / "final_editor_record.json", out / f"{w.name}_final_editor_record.json")      # every attempt's record stays in git
    for f in w.glob("*.json"):
        if f.name.startswith(("audit", "revise_", "verify_")):
            shutil.copy(f, out / f"{w.name}_{f.name}")
    (out / "article.zh.md").write_text(render.markdown(o, "zh"), encoding="utf-8"); (out / "article.en.md").write_text(render.markdown(o, "en"), encoding="utf-8")
    return rec


# ---------------------------------------------------------------- admission

def verify_final_record(o: dict, ev: dict, rec: dict, base: dict | None) -> list[str]:
    render.finalize(o); p = []
    if rec.get("record_type") != "final_editor" or rec.get("schema") != RECORD_SCHEMA:
        return ["not a final-editor record of schema " + RECORD_SCHEMA]
    ed = rec.get("editor") or {}
    if not (ed.get("name") and ed.get("model") and ed.get("cli_version")):
        p.append("editor identity incomplete (name/model/cli_version)")
    if rec.get("final_content_sha256") != o["content_sha256"]:
        p.append("article content differs from the final-editor record")
    if rec.get("evidence_sha256") != editor.sha(ev):
        p.append("evidence differs from the final-editor record")
    if rec.get("failure"):
        p.append(f"final edit did not complete: {rec['failure']}")
    if base is None or base.get("content_sha256") != rec.get("base_content_sha256"):
        p.append("base article missing or not the one the record started from")
    else:
        try:
            if replay(base, rec.get("edits") or [])["content_sha256"] != o["content_sha256"]:
                p.append("edit log does not reproduce the final article")
        except Exception as x:
            p.append(f"edit log does not replay: {x}")
    paths = [q for q, _, _ in editor.fields(o)]
    if _coverage_problems(rec.get("audit") or {}, paths):
        p.append("audit does not cover every field")
    last = (rec.get("rounds") or [{}])[-1].get("verify") or {}
    if last.get("_content_sha256") != o["content_sha256"]:
        p.append("final verify pass not bound to the final content")
    elif verify_schema(paths)({k: v for k, v in last.items() if not k.startswith("_")}):
        p.append("final verify pass invalid or incomplete")
    elif any(i.get("severity") in ("fix", "block") and f"V{len(rec['rounds'])}-{i['id']}" not in
             {x["id"] for x in rec.get("issues", []) if x.get("disposition") in ("fixed", "rejected")} for i in last.get("issues", [])):
        p.append("final verify pass raised fix/block issues that are not closed")
    f_now, _ = checks.check(o, ev); now_at = {m.split()[0] for lvl, m in f_now if lvl in ("BLOCK", "FIX")}
    for i in rec.get("issues") or []:
        if i.get("severity") not in ("fix", "block"):
            continue
        if i.get("origin") == "checker" and i.get("disposition") is None and i["problem"].removeprefix("checker: ").split()[0] not in now_at:
            continue                     # the checker no longer reports anything at that location on this exact content
                                         # (keyed by location, so rewording a checker message cannot close an issue)
        d = i.get("disposition")
        if d == "rejected" and not (i.get("evidence") and all(quote_ok(ev, c) for c in i["evidence"])):
            p.append(f"issue {i['id']} rejected without a verifiable evidence quote")
        elif d == "fixed" and not any(i["id"] in e.get("issues", []) for e in rec.get("edits") or []):
            p.append(f"issue {i['id']} marked fixed but no edit cites it")
        elif d == "duplicate" and not any(x["id"] == i.get("same_as") and x.get("disposition") in ("fixed", "rejected") for x in rec["issues"]):
            p.append(f"issue {i['id']} is a duplicate of an issue that is not closed")
        elif d not in ("fixed", "rejected", "duplicate"):
            p.append(f"issue {i['id']} open: {str(i.get('problem'))[:100]}")
    inh = {i["id"] for i in rec.get("inherited") or []}
    if inh - {i["id"] for i in rec.get("issues") or []}:
        p.append(f"inherited issues not carried into the record: {sorted(inh - {i['id'] for i in rec['issues']})[:5]}")
    f, _ = checks.check(o, ev)
    p += [f"checker {lvl}: {m[:120]}" for lvl, m in f if lvl in ("BLOCK", "FIX")]
    return p


def admit(db, article_path: Path, evidence_path: Path, rec: dict, exception=None) -> dict:
    o = json.loads(Path(article_path).read_text(encoding="utf-8")); ev = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    bp = Path(article_path).parent / "base_article.json"
    base = json.loads(bp.read_text(encoding="utf-8")) if bp.exists() else None
    problems = verify_final_record(o, ev, rec, base)
    if exception:
        problems.append("exceptions are not accepted for final-editor records: every issue is fixed or rejected with evidence")
    cur = state.get(db, o["edition_id"])
    if not cur or cur["status"] != "pending_review":
        problems.append(f"edition status is {cur['status'] if cur else 'unknown'}, not pending_review")
    if problems:
        return {"admitted": False, "edition_id": o["edition_id"], "problems": problems}
    ed = rec["editor"]
    approval = f"final-editor: {ed['name']} ({ed.get('model_reported') or ed['model']}, Claude Code {ed['cli_version']}); record {editor.sha(rec)[:12]}"
    eid = o.get("episode_id") or cur["episode_id"]
    registry.set_status(db, eid, "checked")
    state.transition(db, o["edition_id"], "prepared", note="final-editor record verified", path=str(Path(article_path).resolve()))
    state.transition(db, o["edition_id"], "checked", note=f"admitted: {approval}", content_sha256=o["content_sha256"], reason="",
                     approval=approval, origin=cur.get("origin") or "pipeline")
    return {"admitted": True, "edition_id": o["edition_id"], "approval": approval}

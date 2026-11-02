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

Admission also needs a clean source-context review (context.py) of the exact final content and evidence: the
excerpts read inside their source, every "the source does not say" sentence judged against the reviewed text.
A non-clean review is carried into the next attempt: its additions become the evidence pack and its findings
inherited issues (carried_context). Attempts are bounded (final_editor.max_attempts) and counted since the
edition was last demoted from `checked`.
"""
from __future__ import annotations
import copy, json, re, shutil, time
from pathlib import Path
from . import checks, render, state, registry, editor, schemas, claude_cli, context, evidence
from .config import REPO, data_dir, load_project
from .pipeline import PROMPTS, CODE_REV, _evidence_block, load_prompt
from .textnorm import t2s

RECORD_SCHEMA = "final-editor/v1"
CATEGORIES = {"facts", "attribution", "chronology", "causality", "quotes", "inner_life", "interpretation_label", "parity", "unsupported", "readability", "style"}
CHECKS = {"facts", "attribution", "chronology", "causality", "quotes", "inner_life", "interpretation_label", "parity"}
TIMEOUTS = {"audit": 1800, "revise": 1800, "verify": 1500}
MAX_ROUNDS = int(load_project().get("final_editor", {}).get("max_rounds", 2))
MAX_ATTEMPTS = int(load_project().get("final_editor", {}).get("max_attempts", 3))
MIN_ATTEMPT_MIN = float(load_project().get("final_editor", {}).get("min_minutes_per_attempt", 20))   # do not start an attempt with less job time left
# Runtime health failures (subscription limit, auth, CLI missing or killed by the runtime) are not editorial outcomes:
# they stop the queue, leave the edition pending and do not use up one of its MAX_ATTEMPTS.
HEALTH_MARKERS = ("usage limit", "rate limit", "rate_limit", "limit reached", "overloaded", "authentication", "not logged in",
                  "oauth", "api error", "api_error", "credit balance", "subscription", "not installed", "isolation")


def health_failure(text) -> bool:
    t = str(text or "").lower()
    return any(m in t for m in HEALTH_MARKERS)


def attempts_used(cid: str, db=None) -> int:
    """Final-editor attempts that count toward MAX_ATTEMPTS: runtime health failures excluded, and (with db) only
    attempts since the edition was last demoted from `checked` (a requeue after admission starts a new allowance)."""
    root = data_dir() / "final_edit" / cid; n = 0
    since = (db.execute("SELECT max(at) FROM transition WHERE edition_id=? AND from_status='checked' AND to_status='pending_review'",
                        (cid,)).fetchone()[0] if db is not None else None) or 0
    for a in (root.glob("attempt-*") if root.exists() else []):
        r = a / "final_editor_record.json"
        rec = json.loads(r.read_text(encoding="utf-8")) if r.exists() else {}
        if health_failure(rec.get("failure")) or (rec.get("started_at") or a.stat().st_mtime) < since:
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
        # any category may be a note (editor-in-chief 2026-11-01): only issues that change the main line are fix/block
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


def correct_pack(ev: dict, fix: dict, cache: Path | None = None) -> tuple[dict, list, list]:
    """Owner-scoped correction of an evidence pack (2026-10-31, 胡适: the pack's source title named the wrong chapter, so
    the editor saw every excerpt labelled chapter 8). Existing excerpts keep id, offset, quote and display; a source
    title and an excerpt's locator label may be corrected;
    an added excerpt is cut verbatim from the cached source text (unchanged since the pack was built) between a start
    anchor that occurs exactly once and an end anchor. Returns (new pack, added excerpt ids, errors)."""
    new = copy.deepcopy(ev); added, errs = [], []
    cache = Path(cache or data_dir() / "source_cache")
    for sid, title in (fix.get("titles") or {}).items():
        if sid not in new["sources"] or not str(title).strip():
            errs.append(f"title: unknown source {sid} or empty title"); continue
        new["sources"][sid]["title"] = str(title)
    ids = {x["id"]: x for x in new["excerpts"]}
    for eid, loc in (fix.get("locators") or {}).items():         # the label only: id, offset, quote and display stay as cut
        if eid not in ids or not str(loc).strip():
            errs.append(f"locator: unknown excerpt {eid} or empty label"); continue
        ids[eid]["locator"] = str(loc)
    for a in fix.get("add") or []:
        sid = a.get("source_id"); f = cache / f"{sid}.txt"
        if sid not in new["sources"] or not f.exists():
            errs.append(f"add: source {sid} not in the pack or not cached"); continue
        raw = f.read_bytes()
        if context._sha(raw) != new["sources"][sid].get("text_sha256"):
            errs.append(f"add: cached text of {sid} differs from the text the pack was cut from"); continue
        cjk = context._cjk(raw.decode("utf-8"), new, sid)
        if cjk is None:
            errs.append(f"add: pack offsets of {sid} do not match its cached text"); continue
        norm = evidence.normalise(raw.decode("utf-8"), cjk); st, en = evidence.normalise(str(a.get("start", "")), cjk), evidence.normalise(str(a.get("end", "")), cjk)
        if not st or norm.count(st) != 1:
            errs.append(f"add: start anchor must occur exactly once ({norm.count(st) if st else 0} hits)"); continue
        res, err = evidence.cut(norm, st, en, max_len=400)
        if err:
            errs.append(f"add: {err}"); continue
        off, quote = res
        prefix = next((x["id"].rsplit("-E", 1)[0] for x in new["excerpts"] if x["source_id"] == sid and "-E" in x["id"]), sid)
        n = 1 + max([int(x["id"].rsplit("-E", 1)[1]) for x in new["excerpts"] if x["id"].startswith(prefix + "-E") and x["id"].rsplit("-E", 1)[1].isdigit()] or [0])
        ex = {"id": f"{prefix}-E{n}", "source_id": sid, "locator": f"operator addition: {str(a.get('why', ''))[:120]}", "offset": off,
              "start_anchor_hits": 1, "quote": quote, "display": evidence.dehyphen(quote), "added_by": "operator (owner-scoped local fix)"}
        new["excerpts"].append(ex); added.append(ex["id"])
    return new, added, errs


META_FIELD = re.compile(r"^(sources\.\d+\.citation|further_reading\.\d+\.title)$")   # citation metadata only a local fix may correct


def apply_changes(o: dict, ev: dict, changes: list, *, meta: bool = False) -> tuple[list, list]:
    """Full-field replacements of text (.zh/.en), ev lists and kinds (and, for a local fix, citation metadata).
    Returns (applied, failed)."""
    ev_ids = {e["id"] for e in ev["excerpts"]}; applied, failed = [], []
    for c in changes or []:
        try:
            path = c["path"]; r, k = editor.ref(o, path); before = r[k]
            if meta and META_FIELD.match(path):
                new = c.get("text")
                if not isinstance(new, str) or not new.strip():
                    raise ValueError("text must be a non-empty string")
            elif k in ("zh", "en"):
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


def carried_context(cid: str, o: dict, ev: dict) -> tuple[dict, dict, list] | None:
    """A non-clean article-mode context review of exactly this base text: (record, evidence incl. its additions, issues).
    The expanded pack must keep every original excerpt unchanged."""
    d = OUT_ROOT / cid / "final"; rp, ep = d / "context_review.json", d / "context_evidence.json"
    if not rp.exists():
        return None
    rec = json.loads(rp.read_text(encoding="utf-8"))
    if rec.get("mode") != "article" or rec.get("outcome") != "needs_work" or rec.get("content_sha256") != o["content_sha256"] \
            or rec.get("evidence_in_sha256") != editor.sha(ev):
        return None
    new = json.loads(ep.read_text(encoding="utf-8")) if ep.exists() else ev
    old = {e["id"]: e for e in ev["excerpts"]}
    if editor.sha(new) != rec.get("evidence_sha256") or any(old[i] != next((x for x in new["excerpts"] if x["id"] == i), None) for i in old):
        return None
    return rec, new, context.issues_for_editor(rec)


def revise_base(cid: str, db, new_article: dict, reason: str) -> dict:
    """Owner-authorized whole-article revision of an admitted edition (e.g. the 2026-10-31 reader-first abridgment).
    The admitted revision is archived intact (samples/auto/<cid>/revisions/rev<N>/: article, evidence, every record,
    context review); the new text must be the next revision of the same edition, cite only evidence in the pack and pass
    the deterministic checker without BLOCK. It becomes the base of the next final-editor attempt; the authorization is
    recorded next to it. Nothing is admitted here: the caller demotes the edition and runs the usual checks once."""
    cur = state.get(db, cid); out = OUT_ROOT / cid / "final"
    problems, old = current_eligibility(db, cid)
    if problems or old is None:
        return {"revised": False, "reason": "only an edition admitted now can be revised: " + "; ".join(problems)[:300]}
    o = copy.deepcopy(new_article); render.finalize(o)
    ev = json.loads((out / "evidence.json").read_text(encoding="utf-8"))
    p = []
    if o.get("edition_id") != cid or o.get("revision") != old["revision"] + 1:
        p.append(f"must be {cid} revision {old['revision'] + 1}")
    findings, _ = checks.check(o, ev)
    p += [f"checker BLOCK: {m}" for lvl, m in findings if lvl == "BLOCK"]
    if p:
        return {"revised": False, "reason": "; ".join(p)[:500]}
    arch = OUT_ROOT / cid / "revisions" / f"rev{old['revision']}"
    if arch.exists():
        return {"revised": False, "reason": f"{arch} already exists"}
    shutil.copytree(out, arch)
    auth = {"edition_id": cid, "reason": reason, "at": time.time(), "by": "operator under owner authorization",
            "from_revision": old["revision"], "from_content_sha256": old["content_sha256"], "from_approval": cur.get("approval"),
            "to_revision": o["revision"], "to_base_content_sha256": o["content_sha256"], "archived": str(arch.relative_to(REPO)) if arch.is_relative_to(REPO) else str(arch),
            "attempts_before": attempts_used(cid), "length": o["length"], "reading_minutes": o["reading_minutes"]}
    (OUT_ROOT / cid / "revisions" / f"rev{o['revision']}_authorization.json").write_text(json.dumps(auth, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "article.json").write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "article.zh.md").write_text(render.markdown(o, "zh"), encoding="utf-8"); (out / "article.en.md").write_text(render.markdown(o, "en"), encoding="utf-8")
    return {"revised": True, **auth}


def evidence_added_since_last_attempt(cid: str) -> list[str]:
    """Excerpt ids the latest context review added to the evidence, for a text the final editor *passed*
    (verify_final_record clean): the next attempt has genuinely new input, not a retry of identical inputs."""
    d = OUT_ROOT / cid / "final"; prior = prior_final(cid)
    if not prior or prior.get("failure") or not (d / "article.json").exists() or not (d / "evidence.json").exists():
        return []
    o = json.loads((d / "article.json").read_text(encoding="utf-8")); render.finalize(o)
    ev = json.loads((d / "evidence.json").read_text(encoding="utf-8"))
    base = json.loads((d / "base_article.json").read_text(encoding="utf-8")) if (d / "base_article.json").exists() else None
    if verify_final_record(copy.deepcopy(o), ev, prior, base):
        return []
    cc = carried_context(cid, o, ev)
    if not cc:
        return []
    have = {e["id"] for e in ev["excerpts"]}
    return [x["id"] for x in cc[1]["excerpts"] if x["id"] not in have]


def awaiting_context(cid: str) -> bool:
    """The latest final-editor record verifies for the current final text (verify_final_record, as at admission) and no
    completed context review of that exact text exists yet."""
    d = OUT_ROOT / cid / "final"; prior = prior_final(cid)
    if not prior or prior.get("failure") or not (d / "article.json").exists() or not (d / "evidence.json").exists():
        return False
    o = json.loads((d / "article.json").read_text(encoding="utf-8")); render.finalize(o)
    base = json.loads((d / "base_article.json").read_text(encoding="utf-8")) if (d / "base_article.json").exists() else None
    if verify_final_record(copy.deepcopy(o), json.loads((d / "evidence.json").read_text(encoding="utf-8")), prior, base):
        return False                                   # the same verification admission uses, not the record's own outcome field
    if operator_issues(cid, o):
        return False                                   # an editorial request on this text needs an attempt first
    cp = d / "context_review.json"
    if not cp.exists():
        return True
    c = json.loads(cp.read_text(encoding="utf-8"))
    return not (c.get("content_sha256") == o["content_sha256"] and c.get("outcome") in ("clean", "needs_work"))


def write_operator_issues(cid: str, problems: list[str], reason: str) -> Path:
    """A recorded editorial request (e.g. "the Chinese is much thinner than the English") for the next attempt, bound to
    the current final text; the final editor must judge it like any inherited issue (valid -> fix, invalid -> quote)."""
    d = OUT_ROOT / cid / "final"; o = json.loads((d / "article.json").read_text(encoding="utf-8")); render.finalize(o)
    rec = {"content_sha256": o["content_sha256"], "reason": reason, "at": time.time(),
           "issues": [{"id": f"O{k + 1}", "source": "operator request", "where": "", "problem": x, "suggestion": None} for k, x in enumerate(problems)]}
    (d / "operator_issues.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return d / "operator_issues.json"


def operator_issues(cid: str, o: dict) -> list[dict]:
    p = OUT_ROOT / cid / "final" / "operator_issues.json"
    if not p.exists():
        return []
    rec = json.loads(p.read_text(encoding="utf-8"))
    return rec["issues"] if rec.get("content_sha256") == o["content_sha256"] else []


def run_context(cid: str, *, call=None, cache: Path | None = None) -> dict:
    """Article-mode source-context review of the current final text (samples/auto/<cid>/final). Writes
    context_review.json (+ context_evidence.json when it cut additions) next to the article and returns the record."""
    d = OUT_ROOT / cid / "final"
    o = json.loads((d / "article.json").read_text(encoding="utf-8")); ev = json.loads((d / "evidence.json").read_text(encoding="utf-8"))
    render.finalize(o)
    stamp = time.strftime("%Y%m%dT%H%M%S"); k = 1
    while (d / f"context-{stamp}_review.json").exists():          # every review keeps its own file, even within one second
        k += 1; stamp = f"{time.strftime('%Y%m%dT%H%M%S')}-{k}"
    rec, new_ev = context.review(o, ev, Path(cache or data_dir() / "source_cache"), data_dir() / "context" / cid / stamp, call=call, cid=cid)
    (d / f"context-{stamp}_review.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")   # every review stays in git
    if rec.get("outcome") in ("clean", "needs_work"):
        (d / "context_review.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        ce = d / "context_evidence.json"
        if rec.get("additions"):
            ce.write_text(json.dumps(new_ev, ensure_ascii=False, indent=1), encoding="utf-8")
        elif ce.exists():
            ce.unlink()
    return rec


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
    cx = carried_context(cid, o, ev)
    if cx:
        ev = cx[1]
    (w / "base_article.json").write_text(json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")
    (w / "evidence.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    paths = [p for p, _, _ in editor.fields(o)]
    prior = prior_final(cid)
    inh = carried_issues(prior, o, ev) if prior else inherited_issues(cid, o, ev)   # MiMo issues were all decided in the first attempt
    if cx:                                             # source-context findings on this base text, with the evidence they added
        inh += [dict(i, id=f"X{k + 1}") for k, i in enumerate(cx[2])]
    inh += operator_issues(cid, base)                  # recorded editorial requests bound to this base text
    cont = contamination(cid, ev)
    t0 = time.time(); caller = editor.Caller(w, cid, call)
    rec = {"record_type": "final_editor", "schema": RECORD_SCHEMA, "candidate_id": cid, "edition_id": o["edition_id"],
           "editor": dict(EDITOR, model=claude_cli.MODEL, cli_version=claude_cli.version() if call is claude_cli.call else "test-double"),
           "code_rev": CODE_REV, "started_at": t0, "base_source": str(src[0].relative_to(REPO)) if src[0].is_relative_to(REPO) else str(src[0]),
           "base_content_sha256": base["content_sha256"], "evidence_sha256": editor.sha(ev), "operator_note": operator_note,
           "model_record_sha256": editor.sha(json.loads(_latest_model_record(cid).read_text())) if _latest_model_record(cid) else None,
           "prior_record_sha256": editor.sha(prior) if prior else None, "attempt": w.name,
           "context_review_sha256": editor.sha(cx[0]) if cx else None,
           "inherited": inh, "contamination": cont, "issues": [], "edits": [], "rounds": []}
    ctx = (f"\n\n【遗留问题】\n{json.dumps(inh, ensure_ascii=False, indent=1)}\n\n【已知污染】\n{json.dumps(cont, ensure_ascii=False, indent=1)}"
           f"\n\n【必须覆盖的字段路径】\n{json.dumps(paths, ensure_ascii=False)}")
    audit = caller("audit", f"{load_prompt('final_audit')}\n\n{_view(o, ev, ctx)}", TIMEOUTS["audit"],
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
            rev = caller(f"revise_r{rnd}", f"{load_prompt('final_revise')}\n\n{_view(o, ev)}\n\n【问题清单】\n"
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
        ver = caller(f"verify_r{rnd}", f"{load_prompt('final_verify')}\n\n{_view(o, ev)}\n\n【必须覆盖的字段路径】\n{json.dumps(paths, ensure_ascii=False)}",
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


LOCAL_FIX_MAX_FIELDS = 4          # per named issue: e.g. one sentence's field in zh + en, plus a neighbouring field for a transition


def local_fix(cid: str, db, changes: list, issue_ids: list[str], reason: str, *, call=None, operator_issues: list[dict] | None = None,
              pack_fix: dict | None = None, rejections: list[dict] | None = None, cache: Path | None = None,
              basis: dict | None = None, wide: bool = False) -> dict:
    """A recorded *local* fix of open final-editor issues (owner rule 2026-10-31): small, evidence-backed wording or
    attribution corrections, not a whole-article retry. Allowed only for open fix issues of the latest record that carry
    a verifiable evidence quote, for the fix issues of a needs-work context review bound to this exact text (CTX-X<n>,
    each with the reviewer's source quote; the pack expanded by that review is adopted, every old excerpt unchanged), or
    for owner-instructed operator issues; and only on the fields those issues name (zh/en text, or a source citation /
    further-reading title; <= LOCAL_FIX_MAX_FIELDS per issue). It may also correct the pack (correct_pack: a source
    title, verbatim cuts; old excerpts unchanged) and reject open issues with quotes verified in the corrected pack. The
    change is appended to the same record's edit log (so admission still replays base -> final), then a fresh full
    verify pass runs on the exact new text; anything it raises stays open. That pass reads the whole article but is scoped
    (editor-in-chief 2026-11-01): fix/block only on the changed fields, or on anything that changes the main line; the rest
    were already verified (wide=True drops the scope, for a fix that touches the core judgment). Runs in localfix-* (not counted as an
    attempt; attempt counts are untouched). Context review and admission follow as usual."""
    call = call or claude_cli.call
    if call is claude_cli.call:
        pre = claude_cli.preflight()
        if pre:
            return {"candidate_id": cid, "outcome": "not_run", "reason": "; ".join(pre)}
    out = OUT_ROOT / cid / "final"; rec = prior_final(cid)
    if not rec or rec.get("failure"):
        return {"candidate_id": cid, "outcome": "refused", "reason": "local fix needs a completed final-editor record with open issues"}
    o = json.loads((out / "article.json").read_text(encoding="utf-8")); render.finalize(o)
    ev = json.loads((out / "evidence.json").read_text(encoding="utf-8"))
    if rec.get("final_content_sha256") != o["content_sha256"] or rec.get("evidence_sha256") != editor.sha(ev):
        return {"candidate_id": cid, "outcome": "refused", "reason": "article/evidence differ from the latest record"}
    carried = carried_context(cid, o, ev)                # a needs-work context review of exactly this text, or None
    if rec.get("outcome") != "pending_review" and not carried:
        return {"candidate_id": cid, "outcome": "refused", "reason": "local fix needs a completed final-editor record with open issues "
                                                                     "or a needs-work context review of its text"}
    issues = {i["id"]: i for i in rec["issues"]}; problems = []
    ctx = {}
    if carried:
        crec, new_ev, cx = carried
        ctx = {f"CTX-{i['id']}": {"id": f"CTX-{i['id']}", "path": i["where"], "category": "context", "severity": "fix",
                                  "problem": i["problem"], "origin": f"source-context review {crec.get('started_at')} (content {crec['content_sha256'][:12]})",
                                  "evidence": []} for i in cx if i.get("where")}
    for k, x in enumerate(operator_issues or []):        # owner-instructed wording fixes: the basis is the owner's instruction
        if not (x.get("path") and x.get("problem")):
            problems.append("operator issue needs FIELD_PATH|PROBLEM"); continue
        oid = f"OP{len([i for i in issues if str(i).startswith('OP')]) + 1}"
        issues[oid] = {"id": oid, "path": x["path"], "category": "readability", "severity": "fix", "problem": x["problem"],
                       "origin": "operator: owner instruction (local fix)", "evidence": []}
        issue_ids = list(issue_ids) + [oid]
    if not issue_ids and not rejections:
        problems.append("name at least one open issue or operator issue")
    for k in issue_ids:
        i = issues.get(k)
        if str(k).startswith("OP"):
            continue
        if k in ctx:                                     # the reviewer's quote was checked against the source text at review time
            issues[k] = ctx[k]; continue
        if not i or k not in (rec.get("open_issues") or []):
            problems.append(f"{k}: not an open issue of the latest record")
        elif basis and k in basis:                       # the operator's own basis: every quote must be verbatim in the pack
            if not (basis[k] and all(quote_ok(ev, c) for c in basis[k])):
                problems.append(f"{k}: the supplied basis quotes are not verbatim in the evidence pack")
            else:
                issues[k] = dict(i, basis_supplied=basis[k])
        elif not (i.get("evidence") and all(quote_ok(ev, c) for c in i["evidence"])):
            problems.append(f"{k}: no verifiable evidence quote (not a clear-basis local fix)")
    allowed = {issues[k].get("path") for k in issue_ids if k in issues}
    fields = {c.get("path") for c in changes}
    if len(fields) > LOCAL_FIX_MAX_FIELDS * max(1, len(issue_ids)):
        problems.append(f"{len(fields)} fields changed (> {LOCAL_FIX_MAX_FIELDS} per issue): use an attempt, not a local fix")
    for c in changes:
        path = str(c.get("path")); base_path, _, lang = path.rpartition(".")
        if not ((META_FIELD.match(path) and path in allowed) or (lang in ("zh", "en", "ev") and base_path in allowed)):
            problems.append(f"{c.get('path')}: outside the fields the issues name {sorted(allowed)}")
    pack_note = None
    if pack_fix:
        new_ev, added, perr = correct_pack(ev, pack_fix, cache)
        problems += perr
        pack_note = {"from": editor.sha(ev), "to": editor.sha(new_ev), "titles": pack_fix.get("titles") or {},
                     "locators": pack_fix.get("locators") or {}, "added": added, "reason": reason}
    for x in rejections or []:
        k = x.get("issue")
        if k not in (rec.get("open_issues") or []):
            problems.append(f"reject {k}: not an open issue of the latest record")
        elif not (x.get("rationale") and x.get("evidence") and all(quote_ok(new_ev if pack_fix else ev, c) for c in x["evidence"])):
            problems.append(f"reject {k}: needs a rationale and quotes verified in the (corrected) pack")
    if problems:
        return {"candidate_id": cid, "outcome": "refused", "reason": "; ".join(problems)}
    rec = copy.deepcopy(rec)
    if pack_note:
        ev = new_ev; rec["evidence_sha256"] = editor.sha(ev); rec["evidence_corrected"] = (rec.get("evidence_corrected") or []) + [pack_note]
    if carried and editor.sha(carried[1]) != editor.sha(ev):    # cite what the context review cut from the source (old excerpts kept)
        rec["evidence_expanded"] = (rec.get("evidence_expanded") or []) + [
            {"from": editor.sha(ev), "to": editor.sha(carried[1]), "by": f"source-context review {carried[0].get('started_at')}",
             "added": [a["id"] for a in carried[0].get("additions") or []]}]
        ev = carried[1]; rec["evidence_sha256"] = editor.sha(ev)
    root = data_dir() / "final_edit" / cid; w = root / f"localfix-{rec['attempt']}-{len(list(root.glob('localfix-*'))) + 1}"
    w.mkdir(parents=True, exist_ok=True)
    applied, failed = apply_changes(o, ev, [dict(c, issues=list(issue_ids)) for c in changes], meta=True)
    if failed or not (applied or pack_fix or rejections):
        return {"candidate_id": cid, "outcome": "refused", "reason": f"changes did not apply: {failed or 'no change'}"}
    render.finalize(o); rec["edits"] += applied
    for k in issue_ids:
        issues[k].update(disposition="fixed", decided_in=w.name, rationale=f"local fix: {reason}")
    for x in rejections or []:
        issues[x["issue"]].update(disposition="rejected", decided_in=w.name, rationale=f"local fix: {x['rationale']}", evidence=x["evidence"])
    paths = [p for p, _, _ in editor.fields(o)]; caller = editor.Caller(w, cid, call); rnd = len(rec["rounds"]) + 1
    findings, _ = checks.check(o, ev)
    r = {"round": rnd, "local_fix": {"by": "operator (owner rule 2026-10-31: small evidence-backed fixes)", "reason": reason,
                                     "issues": list(issue_ids), "rejected": [x["issue"] for x in rejections or []],
                                     "pack_corrected": pack_note, "at": time.time(), "dir": w.name},
         "issues_in": list(issue_ids), "changes_applied": len(applied), "changes_failed": [], "still_open": [], "checker_after": findings,
         "content_sha256_after": o["content_sha256"]}
    meta = [f"{p} ⟨{editor.ref(o, p)[0][editor.ref(o, p)[1]]}⟩" for p in sorted(fields) if META_FIELD.match(p)]
    extra = ("\n\n【本次局部修正同时改动的来源元数据（请一并核对其与证据包是否一致；有问题记在 uncertainty_note 下）】\n" + "\n".join(meta)) if meta else ""
    if not wide:
        extra += ("\n\n【本次核查范围：局部修正后只重查受影响部分】\n本次只改动了这些字段：" + "、".join(sorted({re.sub(r"\.(zh|en)$", "", f) for f in fields if f}))
                  + "。fields 仍要覆盖全部字段路径，但只对这些字段（中英文）提出 fix/block。其他字段此前已通过核查：除非发现会改变主线的问题"
                  "（人物关系错误、关键因果错误、引文曲解、严重误导、编造），否则至多记 note。")
    ver = caller(f"verify_r{rnd}", f"{load_prompt('final_verify')}\n\n{_view(o, ev, extra)}\n\n【必须覆盖的字段路径】\n{json.dumps(paths, ensure_ascii=False)}",
                 TIMEOUTS["verify"], "\n\n[Reply with one valid JSON object only, matching the schema.]", validate=verify_schema(paths))
    rec.setdefault("local_fixes", []).append(r["local_fix"] | {"edits": applied})
    rec["calls_before_local_fix"] = (rec.get("calls_before_local_fix") or []) + (rec.get("calls") or [])
    (w / "base_article.json").write_text((out / "base_article.json").read_text(encoding="utf-8"), encoding="utf-8")
    (w / "evidence.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    if ver is None:
        rec["rounds"].append(r); return _finish(rec, w, o, cid, caller, f"local-fix verify failed: " + _why(caller), issues)
    ver["_content_sha256"] = o["content_sha256"]; r["verify"] = ver
    for i in ver["issues"]:
        if i["severity"] in ("fix", "block"):
            vid = f"V{rnd}-{i['id']}"; issues[vid] = dict(i, id=vid, origin=f"final-editor verify after local fix (round {rnd})")
    for lvl, msg in findings:
        if lvl in ("BLOCK", "FIX"):
            k = f"C{rnd}-{len(issues) + 1}"; issues[k] = {"id": k, "path": "", "category": "unsupported", "severity": lvl.lower(),
                                                          "problem": f"checker: {msg}", "origin": "checker"}
    rec["rounds"].append(r)
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
               finished_at=time.time(), calls=[{k: m.get(k) for k in ("step", "attempt", "wall_s", "json_ok", "schema_ok", "schema_problems", "killed", "prompts")}
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
        checker_derived = i.get("origin") == "checker" or str(i.get("problem", "")).startswith("checker: ")   # incl. carried from a previous attempt
        if checker_derived and i["problem"].removeprefix("checker: ").split()[0] not in now_at:
            continue                     # the deterministic checker no longer reports anything at that location on this exact
                                         # content, whatever the model labelled it (keyed by location, so rewording cannot close it)
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


ADMITTED = ("checked", "scheduled", "archived", "site_committed", "site_live", "email_pending", "complete")


def current_eligibility(db, edition_id: str, article_path: Path | None = None, cache: Path | None = None) -> tuple[list[str], dict | None]:
    """Is this edition editorially admitted *now*? Re-verifies from the canonical records, never from a status field in
    the JSON handed in: edition state is admitted; the file is the edition's admitted path with the state's revision and
    content hash; the final-editor record next to it verifies against that article, its evidence and base article
    (verify_final_record, as at admission); a clean source-context review is bound to that content and evidence
    (context.record_problems, as at admission); and the state's approval names that record. An owner-approved sample
    (approve-sample) needs no final-editor record but the same clean context review. Returns (problems, article)."""
    cur = state.get(db, edition_id)
    if not cur:
        return [f"{edition_id} is not a registered edition"], None
    if cur["status"] not in ADMITTED:
        return [f"{edition_id} is {cur['status']}, not admitted" + (f" ({cur['reason'][:120]})" if cur.get("reason") else "")], None
    if not cur.get("path") or not Path(cur["path"]).exists():
        return [f"{edition_id}: admitted article file missing"], None
    path = Path(cur["path"]).resolve()
    if article_path is not None and Path(article_path).resolve() != path:
        return [f"{article_path} is not the admitted article of {edition_id} ({path})"], None
    if cur["status"] != "checked":                       # scheduled or later: the path is the archived copy; re-verify its source
        return [], None
    return admitted_file_problems(path, cur, cache)


def admitted_file_problems(path: Path, cur: dict, cache: Path | None = None) -> tuple[list[str], dict | None]:
    """The admission evidence of one admitted article file, re-verified (see current_eligibility)."""
    edition_id = cur["edition_id"]
    o = json.loads(Path(path).read_text(encoding="utf-8")); render.finalize(o); p = []
    if o.get("edition_id") != edition_id or o.get("revision") != cur["revision"] or o["content_sha256"] != cur["content_sha256"]:
        p.append("article file differs from the admitted edition (id, revision or content hash)")
    d = Path(path).parent; files = {n: d / f"{n}.json" for n in ("final_editor_record", "evidence", "base_article")}
    if (cur.get("origin") or "pipeline") == "sample" and str(cur.get("approval") or "").startswith("sample-approved"):
        evp = d / "evidence.json" if (d / "evidence.json").exists() else REPO / "samples" / f"evidence_{d.name}.json"
        if not evp.exists():
            return p + ["approved sample: evidence pack missing"], o       # owner approval replaces the final-editor record,
        ev = json.loads(evp.read_text(encoding="utf-8"))                     # not the source-context gate
        return p + context.record_problems(_context_of(path), o, ev, cache), o
    if not files["final_editor_record"].exists() or not files["evidence"].exists():
        return p + ["no final-editor record and evidence next to the admitted article"], o
    rec = json.loads(files["final_editor_record"].read_text(encoding="utf-8")); ev = json.loads(files["evidence"].read_text(encoding="utf-8"))
    base = json.loads(files["base_article"].read_text(encoding="utf-8")) if files["base_article"].exists() else None
    p += verify_final_record(json.loads(json.dumps(o)), ev, rec, base)
    p += context.record_problems(_context_of(path), o, ev, cache)
    if not str(cur.get("approval") or "").endswith(f"record {editor.sha(rec)[:12]}"):
        p.append("the admission does not name this final-editor record")
    return p, o


def _context_of(article_path: Path) -> dict | None:
    p = Path(article_path).parent / "context_review.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


SEND_BODY_KEYS = ("title", "dek", "sections", "reflection", "uncertainty_note", "sources", "further_reading", "category")


def send_problems(db, o: dict, cache: Path | None = None) -> list[str]:
    """May this exact object be emailed for real? (`hip send/retry-send --real`, scheduled publication.) A checked edition
    must be eligible now (current_eligibility) and be that admitted content; an archived/published copy must carry
    admitted_from (written by publish.archive) whose source file still verifies (record + clean context review, with the
    approval recorded at admission) and whose body equals this object's. TEST objects go only through test-edition."""
    if o.get("status") == "test":
        return ["TEST objects are sent only by `hip test-edition send` (its own admission and window checks)"]
    cur = state.get(db, o.get("edition_id"))
    if not cur:
        return [f"{o.get('edition_id')} is not a registered edition"]
    af = o.get("admitted_from")
    if not af:
        p, src = current_eligibility(db, o["edition_id"], cache=cache)
        if src is not None and render.finalize(json.loads(json.dumps(o)))["content_sha256"] != src["content_sha256"]:
            p.append("this object is not the admitted content of the edition")
        return p or ([] if src is not None else [f"{o['edition_id']} has no verifiable admitted content (status {cur['status']})"])
    if cur["status"] not in ADMITTED:
        return [f"{o['edition_id']} is {cur['status']}, not admitted"]
    src_cur = dict(cur, path=af["path"], content_sha256=af["content_sha256"], revision=af.get("revision", cur["revision"]), approval=af.get("approval"))
    if not Path(af["path"]).exists():
        return ["admitted source file missing: " + af["path"]]
    p, src = admitted_file_problems(Path(af["path"]), src_cur, cache)
    if src is not None:
        p += [f"{k} differs from the admitted article" for k in SEND_BODY_KEYS if src.get(k) != o.get(k)]
    return p


def adopt(db, edition_id: str, cache: Path | None = None) -> dict:
    """Bring an article finished elsewhere in this repository (e.g. the 2026-11-01 book-supply validation worktree) into
    this data directory through the same admission: samples/auto/<id>/final/ must hold the article, its evidence, the
    final-editor record and a clean source-context review bound to exactly this content and evidence, with the sources
    re-hashed from THIS machine's source cache. The episode is registered first (duplicate check). Nothing is relaxed:
    any mismatch leaves the edition pending with the reasons."""
    out = OUT_ROOT / edition_id / "final"; art, evp, recp = out / "article.json", out / "evidence.json", out / "final_editor_record.json"
    if state.get(db, edition_id):
        return {"adopted": False, "reason": f"already known here: {state.get(db, edition_id)['status']}"}
    if not (art.exists() and evp.exists() and recp.exists()):
        return {"adopted": False, "reason": f"{out}: article, evidence or final-editor record missing"}
    o = json.loads(art.read_text(encoding="utf-8")); render.finalize(o)
    ep = dict(o.get("episode") or {}, episode_id=o.get("episode_id"), title=o["title"]["zh"], category=o["category"])
    eid, v = registry.reserve(db, ep, status="prepared")
    if not eid:
        return {"adopted": False, "reason": f"episode {v[0]}: {v[1]}"}
    state.transition(db, edition_id, "prepared", note="adopted: records from samples/auto (verifying)", episode_id=eid,
                     category=o["category"], path=str(art.resolve()))
    state.transition(db, edition_id, "pending_review", note="adopted: verifying final-editor record and context review",
                     reason="adopt: verifying records")
    r = admit(db, art, evp, json.loads(recp.read_text(encoding="utf-8")), cache=cache)
    if not r.get("admitted"):
        state.transition(db, edition_id, "prepared", note="adopt refused"); state.transition(db, edition_id, "pending_review",
                         note="adopt refused", reason="adopt refused: " + "; ".join(r.get("problems") or [])[:1500])
    return dict(r, adopted=bool(r.get("admitted")))


def admit(db, article_path: Path, evidence_path: Path, rec: dict, exception=None, cache: Path | None = None) -> dict:
    o = json.loads(Path(article_path).read_text(encoding="utf-8")); ev = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    bp = Path(article_path).parent / "base_article.json"
    base = json.loads(bp.read_text(encoding="utf-8")) if bp.exists() else None
    problems = verify_final_record(o, ev, rec, base)
    render.finalize(o); problems += context.record_problems(_context_of(article_path), o, ev, cache)
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
                     approval=approval, origin=cur.get("origin") or "pipeline", revision=o.get("revision") or cur["revision"])
    return {"admitted": True, "edition_id": o["edition_id"], "approval": approval}

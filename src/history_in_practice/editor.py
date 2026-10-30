"""Editor stage: pending model draft -> bounded model edit rounds -> re-check ->
re-review (Chinese facts) + parity review (English vs Chinese) -> editor record.

The record binds the outcome to exactly what was reviewed:
* ``final_content_sha256`` (render.canonical of the edited article),
* ``evidence_sha256`` (the evidence pack the edits and reviews used),
* the final review and parity results, each tagged with the content hash it saw,
* every edit (before/after/reason/issues) and every issue's disposition.

``admit`` (cli and ``admit_with_record``) refuses an article whose content or
evidence no longer matches its record, and refuses remaining fix/block/BLOCK
issues unless a named exception reason is given. Nothing here lowers the
review threshold: unresolved drafts stay ``pending_review``.
"""
from __future__ import annotations
import copy, hashlib, json, time
from pathlib import Path
from . import checks, render, llm, state, registry
from .config import REPO
from .pipeline import PROMPTS, REFUSAL, CODE_REV, _evidence_block

from .config import load_project as _lp
MAX_ROUNDS = int(_lp().get("editor", {}).get("max_rounds", 2))
TIMEOUTS = {"edit": 1500, "review": 1200, "parity": 1200}
EDITOR_NAME = "hermes-isolated editor (prompts/edit_zh_en.md)"


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def ref(o, path):
    """Resolve 'sections.<id>.<i>.<lang>', 'sections.<id>.heading.<lang>', 'sections.<id>.paras' or a dotted dict path."""
    parts = path.split(".")
    if parts[0] == "sections":
        sec = next(s for s in o["sections"] if s["id"] == parts[1])
        if parts[2] == "paras":
            return sec, "paras"
        return (sec["heading"], parts[3]) if parts[2] == "heading" else (sec["paras"][int(parts[2])], parts[3])
    cur = o
    for k in parts[:-1]:
        cur = cur[k]
    return cur, parts[-1]


def fields(o) -> list[tuple[str, str, str]]:
    """(path-without-lang, zh, en) for every reader-visible text field."""
    out = [("title", o["title"]["zh"], o["title"]["en"]), ("dek", o["dek"]["zh"], o["dek"]["en"])]
    for s in o["sections"]:
        out.append((f"sections.{s['id']}.heading", s["heading"]["zh"], s["heading"]["en"]))
        for i, p in enumerate(s["paras"]):
            out.append((f"sections.{s['id']}.{i}", p["zh"], p["en"]))
    r = o["reflection"]
    out += [(f"reflection.{k}", r[k]["zh"], r[k]["en"]) for k in ("scenario", "question")]
    out += [(f"reflection.example.{k}", v["zh"], v["en"]) for k, v in r["example"].items()]
    out.append(("uncertainty_note", o["uncertainty_note"]["zh"], o["uncertainty_note"]["en"]))
    return out


def article_view(o) -> str:
    lines = []
    for s in o["sections"]:
        for i, p in enumerate(s["paras"]):
            lines.append(f"[sections.{s['id']}.{i}] kind={p['kind']} ev={','.join(p['ev'])}")
    meta = "\n".join(lines)
    body = "\n".join(f"{path}.zh ⟨{zh}⟩\n{path}.en ⟨{en}⟩" for path, zh, en in fields(o))
    return f"<paragraph_kinds_and_evidence>\n{meta}\n</paragraph_kinds_and_evidence>\n\n<fields>\n{body}\n</fields>"


def zh_view(o) -> dict:
    """The Chinese article in the draft format the review prompt was written for."""
    return {"title": o["title"]["zh"], "dek": o["dek"]["zh"],
            "sections": [{"id": s["id"], "heading": s["heading"]["zh"],
                          "paras": [{"t": p["zh"], "kind": p["kind"], "ev": p["ev"]} for p in s["paras"]]} for s in o["sections"]],
            "reflection": {"type": o["reflection"].get("type"), **{k: o["reflection"][k]["zh"] for k in ("scenario", "question")},
                           "example": {k: v["zh"] for k, v in o["reflection"]["example"].items()}},
            "uncertainty_note": o["uncertainty_note"]["zh"]}


def parity_view(o) -> str:
    return "\n\n".join(f"{path}\nZH: {zh}\nEN: {en}" for path, zh, en in fields(o))


class Caller:
    """One logged model call with a single retry on invalid JSON; refusals are not retried."""
    def __init__(self, outdir: Path, cid: str, call=None):
        self.outdir, self.cid, self.call, self.metrics = outdir, cid, call or llm.call, []

    def __call__(self, name, prompt, timeout, retry_suffix):
        for attempt in (1, 2):
            r = self.call(prompt if attempt == 1 else prompt + retry_suffix, timeout_s=timeout)
            m = {k: v for k, v in r.items() if k != "text"}; m.update(step=name, attempt=attempt, candidate=self.cid)
            (self.outdir / f"{name}.a{attempt}.raw.txt").write_text(r["text"], encoding="utf-8")
            try:
                obj = llm.parse_json(r["text"]) if r["rc"] == 0 and not r["killed"] else None
            except ValueError:
                obj = None
            m["json_ok"] = obj is not None
            if obj is None and len(r["text"].strip()) < 400 and REFUSAL.search(r["text"]):
                m["provider_refusal"] = r["text"].strip()[:200]
            with open(self.outdir / "calls.jsonl", "a", encoding="utf-8") as log:
                log.write(json.dumps(dict(m, at=time.time()), ensure_ascii=False) + "\n")
            self.metrics.append(m)
            if obj is not None:
                (self.outdir / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
                return obj
            if "provider_refusal" in m or r["killed"] == "timeout":
                return None
        return None


def collect_issues(review: dict | None, parity: dict | None, findings: list) -> list[dict]:
    out = []
    for i in (review or {}).get("issues", []):
        if i.get("severity") in ("fix", "block"):
            out.append({"id": f"R{len(out) + 1}", "source": "review", "severity": i["severity"],
                        "where": f"{i.get('section')}.{i.get('para')}", "problem": i.get("problem"), "suggestion": i.get("suggestion")})
    for i in (parity or {}).get("issues", []):
        if i.get("severity") == "fix":
            out.append({"id": f"P{len(out) + 1}", "source": "parity", "severity": "fix", "where": i.get("path"),
                        "problem": i.get("problem"), "suggestion": i.get("suggestion")})
    for lvl, msg in findings:
        if lvl in ("BLOCK", "FIX"):
            out.append({"id": f"C{len(out) + 1}", "source": "checker", "severity": lvl, "where": "", "problem": msg, "suggestion": ""})
    return out


def unresolved(issues_in: list, applied: list, dispositions: list) -> list:
    """Issues raised but neither fixed (disposition 'fixed' AND an applied edit citing it) nor rejected with a reason.
    They stay open even if a later review happens not to repeat them."""
    disp = {str(d.get("issue")): d for d in dispositions or [] if isinstance(d, dict)}
    cited = {str(i) for e in applied for i in (e.get("issues") or [])}
    out = []
    for i in issues_in:
        d = disp.get(i["id"], {})
        if d.get("action") == "fixed" and i["id"] in cited:
            continue
        if d.get("action") == "rejected" and str(d.get("reason", "")).strip():
            continue
        out.append(dict(i, open_because="no disposition" if not d else f"disposition '{d.get('action')}' without an applied edit or reason"))
    return out


def apply_edits(o: dict, ev_ids: set, edits: list, ev_changes: list) -> tuple[list, list]:
    applied, failed = [], []
    for e in edits or []:
        try:
            path = e["path"]
            if not path.endswith((".zh", ".en")):
                raise ValueError("path must end in .zh or .en")
            r, k = ref(o, path); before = r[k]
            if not isinstance(before, str) or before.count(e["find"]) != 1 or not e["find"]:
                raise ValueError(f"find occurs {before.count(e['find']) if isinstance(before, str) and e['find'] else 0} times")
            r[k] = before.replace(e["find"], e["replace"])
            applied.append({"path": path, "before": before, "after": r[k], "reason": e.get("reason", ""), "issues": e.get("issues", [])})
        except Exception as x:
            failed.append({"edit": e, "error": f"{type(x).__name__}: {x}"})
    for e in ev_changes or []:
        try:
            r, k = ref(o, e["path"])
            if k != "ev" or not set(e["new"]) <= ev_ids:
                raise ValueError("ev change must target an ev field with known evidence ids")
            if r.get("kind") == "modern" and e["new"]:
                raise ValueError("modern scenes cannot cite evidence")
            before = r[k]; r[k] = list(e["new"])
            applied.append({"path": e["path"], "before": before, "after": r[k], "reason": e.get("reason", ""), "issues": e.get("issues", [])})
        except Exception as x:
            failed.append({"edit": e, "error": f"{type(x).__name__}: {x}"})
    return applied, failed


def reviews(o, ev, caller: Caller, tag: str) -> tuple[dict | None, dict | None]:
    evb = _evidence_block(ev); h = o["content_sha256"]
    rv = caller(f"rereview_{tag}", f"{(PROMPTS / 'review_zh.md').read_text()}\n\n【证据包】\n{evb}\n\n【稿件】\n{json.dumps(zh_view(o), ensure_ascii=False)}",
                TIMEOUTS["review"], "\n\n[只输出一个合法 JSON 对象。]")
    pv = caller(f"parity_{tag}", f"{(PROMPTS / 'parity_en.md').read_text()}\n\n<fields>\n{parity_view(o)}\n</fields>",
                TIMEOUTS["parity"], "\n\n[Reply with one valid JSON object only.]")
    for x in (rv, pv):
        if x is not None:
            x["_content_sha256"] = h
    return rv, pv


def edit(draft_dir: Path, call=None, max_rounds: int = MAX_ROUNDS) -> dict:
    """Run the editor on a pending draft directory. Writes edited.json + editor_record.json; returns the record."""
    d = Path(draft_dir); cid = d.name
    o = json.loads((d / "article.json").read_text(encoding="utf-8")); ev = json.loads((d / "evidence.json").read_text(encoding="utf-8"))
    render.finalize(o); original = copy.deepcopy(o)
    caller = Caller(d, cid, call); ev_ids = {e["id"] for e in ev["excerpts"]}
    review = json.loads((d / "review_zh.json").read_text()) if (d / "review_zh.json").exists() else None
    if review is not None:
        review["_content_sha256"] = "model draft (zh) before English and assembly"
    findings, _ = checks.check(o, ev)
    record = {"candidate_id": cid, "editor": EDITOR_NAME, "code_rev": CODE_REV, "started_at": time.time(),
              "evidence_sha256": sha(ev), "original_content_sha256": o["content_sha256"], "rounds": []}
    issues = collect_issues(review, None, findings)
    seed = d / "seed_issues.json"                      # a later attempt starts from the previous attempt's open issues
    if seed.exists():
        prior = json.loads(seed.read_text(encoding="utf-8"))
        issues = [dict(i, id=f"S{k + 1}", seeded_from=i.get("id")) for k, i in enumerate(prior) if i.get("source") != "checker"] + issues
        record["seeded_issues"] = len(issues) - len(collect_issues(review, None, findings))
    for rnd in range(1, max_rounds + 1):
        if not issues:
            break
        prompt = (f"{(PROMPTS / 'edit_zh_en.md').read_text()}\n\n【证据包】\n{_evidence_block(ev)}\n\n【稿件】\n{article_view(o)}\n\n"
                  f"【待处理问题】\n{json.dumps(issues, ensure_ascii=False, indent=1)}")
        out = caller(f"edit_r{rnd}", prompt, TIMEOUTS["edit"], "\n\n[只输出一个合法 JSON 对象。]")
        rec = {"round": rnd, "issues_in": issues}
        if out is None:
            rec["error"] = "editor model returned no usable JSON"; record["rounds"].append(rec); break
        applied, failed = apply_edits(o, ev_ids, out.get("edits"), out.get("ev_changes"))
        render.finalize(o); findings, _ = checks.check(o, ev)
        rv, pv = reviews(o, ev, caller, f"r{rnd}")
        rec.update(edits_applied=applied, edits_failed=failed, dispositions=out.get("dispositions", []),
                   checker_after=findings, content_sha256_after=o["content_sha256"],
                   review_after=rv, parity_after=pv)
        record["rounds"].append(rec)
        if rv is None or pv is None:
            break
        carried = unresolved(issues, applied, out.get("dispositions"))
        rec["carried_over"] = carried
        fresh = collect_issues(rv, pv, findings)
        issues = [dict(i, id=f"{i['id']}'") for i in carried] + fresh   # carried ids get a prime so they stay distinct
        if not applied:
            break                                   # no progress possible this round
    if not record["rounds"]:                         # nothing flagged: still bind a review to the final content
        rv, pv = reviews(o, ev, caller, "r0"); findings, _ = checks.check(o, ev)
        record["rounds"].append({"round": 0, "issues_in": [], "review_after": rv, "parity_after": pv, "checker_after": findings,
                                 "content_sha256_after": o["content_sha256"]})
        issues = collect_issues(rv, pv, findings) if rv is not None and pv is not None else [{"id": "X", "problem": "review failed"}]
    last = record["rounds"][-1]
    final_reviewed = last.get("content_sha256_after") == o["content_sha256"] and last.get("review_after") and last.get("parity_after")
    remaining = issues if final_reviewed else (issues or [{"id": "X", "source": "editor", "severity": "fix", "problem": "final content was not re-reviewed"}])
    record.update(final_content_sha256=o["content_sha256"], remaining=remaining, final_reviewed=bool(final_reviewed),
                  outcome="admissible" if final_reviewed and not remaining else "pending_review",
                  model_calls=len(caller.metrics), model_wall_s=round(sum(m.get("wall_s", 0) for m in caller.metrics), 1),
                  edits_total=sum(len(r.get("edits_applied", [])) for r in record["rounds"]), finished_at=time.time())
    (d / "edited.json").write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "editor_record.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


def verify_record(o: dict, ev: dict, record: dict) -> list[str]:
    """Problems that make a record unusable for admitting this exact article (empty = bound)."""
    render.finalize(o); problems = []
    if record.get("final_content_sha256") != o["content_sha256"]:
        problems.append("article content differs from the editor record (edited after review?)")
    if record.get("evidence_sha256") != sha(ev):
        problems.append("evidence differs from the editor record")
    if not record.get("final_reviewed"):
        problems.append("final content was not re-reviewed")
    last = (record.get("rounds") or [{}])[-1]
    for k in ("review_after", "parity_after"):
        if (last.get(k) or {}).get("_content_sha256") != o["content_sha256"]:
            problems.append(f"{k} not bound to the final content")
    return problems


def admit_with_record(db, article_path: Path, evidence_path: Path, record: dict, exception: str | None = None) -> dict:
    """Admit an edited pending draft into schedulable inventory, bound to its record."""
    o = json.loads(Path(article_path).read_text(encoding="utf-8")); ev = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    hard = verify_record(o, ev, record)               # never overridable
    f, _ = checks.check(o, ev)
    if checks.blocked(f):
        hard.append("checker BLOCK on the final article")
    soft = [f"remaining {i.get('source', '?')} issue {i.get('id')}: {str(i.get('problem'))[:120]}" for i in record.get("remaining") or []]
    soft += [f"checker FIX: {m[:120]}" for lvl, m in f if lvl == "FIX"]
    if hard or (soft and not exception):
        return {"admitted": False, "edition_id": o["edition_id"], "problems": hard + soft,
                "hint": "" if hard else "remaining FIX-level issues: fix them, or pass --exception REASON for a named, human-approved exception"}
    cur = state.get(db, o["edition_id"])
    if not cur or cur["status"] != "pending_review":
        return {"admitted": False, "edition_id": o["edition_id"], "problems": [f"edition status is {cur['status'] if cur else 'unknown'}, not pending_review"]}
    approval = f"exception: {exception}" if exception else "editor-record"
    eid = o.get("episode_id") or cur["episode_id"]
    registry.set_status(db, eid, "checked")
    state.transition(db, o["edition_id"], "prepared", note="editor record verified", path=str(Path(article_path).resolve()))
    state.transition(db, o["edition_id"], "checked", note=f"admitted: {approval}", content_sha256=o["content_sha256"],
                     reason="", approval=approval, origin=state.get(db, o["edition_id"]).get("origin") or "pipeline")
    return {"admitted": True, "edition_id": o["edition_id"], "approval": approval}

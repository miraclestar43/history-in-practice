"""Automated supply: candidate -> sources -> evidence -> admission -> registry
-> Hermes (zh draft, evidence review, natural English) -> assemble -> checks ->
`pending_review` with reasons. Every draft then goes through the editor stage
(editor.py: bounded edit rounds, re-review of the final Chinese, English parity
review, record bound to the final content) before it can be admitted as
`checked`; nothing here marks a draft schedulable on its own.
"""
from __future__ import annotations
import json, time
from pathlib import Path
from . import sources as src_mod, evidence, registry, render, checks, llm, state, schemas
from .config import REPO, data_dir, load_project

PROMPTS = Path(__file__).with_name("prompts")
import re as _re
import subprocess as _sp


def _code_rev() -> str:
    """Git revision of the code this process loaded (a long-running queue keeps old code)."""
    try:
        return _sp.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


CODE_REV = _code_rev()                         # evaluated once, at import time
REFUSAL = _re.compile(r"rejected because it was considered high risk|content (?:policy|filter)|cannot (?:help|assist) with|I can't (?:help|assist)", _re.I)


def load_candidate(path: Path) -> dict:
    c = json.loads(Path(path).read_text(encoding="utf-8"))
    for k in ("candidate_id", "category", "episode", "sources", "excerpts", "brief"):
        if k not in c:
            raise ValueError(f"candidate missing {k}")
    return c


def fetch_sources(c, cache: Path, refresh=False) -> dict:
    out = {}
    for s in c["sources"]:
        cached = cache / f"{s['id']}.txt"
        meta = cache / f"{s['id']}.meta.json"
        if cached.exists() and meta.exists() and not refresh:
            r = json.loads(meta.read_text())
        else:
            r = src_mod.fetch(s, cache)
            meta.write_text(json.dumps(r, ensure_ascii=False, indent=1))
        r.update(ref=s.get("ref"), title=s.get("title"), basis=s.get("basis"), cjk=s.get("cjk", False))
        out[s["id"]] = r
    return out


def admission(c, fetched, pack, errors) -> list[str]:
    """Return reasons that send the candidate to the pending queue (empty = admit)."""
    reasons = []
    bad = [f"{k}: {v.get('status')}" for k, v in fetched.items() if v.get("status") != "evidence_usable" and k in {e[1] for e in c["excerpts"]}]
    if bad:
        reasons.append("source not evidence_usable: " + "; ".join(bad))
    if errors:
        reasons.append("excerpt errors: " + "; ".join(errors))
    core = set(c.get("core_excerpts") or [c["excerpts"][0][0]])
    if not core <= {e["id"] for e in pack["excerpts"]}:
        reasons.append("core excerpts missing")
    bases = {v.get("basis") for v in pack["sources"].values() if v.get("basis")}
    independent = {b for b in bases if not str(b).endswith("-derived")}
    if len(independent) < 2 and not c.get("single_basis_disclosed"):
        reasons.append("fewer than two independent source bases and no disclosure")
    return reasons


def _evidence_block(pack):
    return "<evidence>\n" + "\n\n".join(
        f"[{e['id']}] 来源：{pack['sources'][e['source_id']]['title']}；位置：{e['locator']}\n{e['display']}" for e in pack["excerpts"]) + "\n</evidence>"


def _s(v):
    """Model output sometimes returns a list where a string is expected."""
    if isinstance(v, list):
        return "\n".join(_s(x) for x in v)
    return "" if v is None else str(v)


def _normalise(d):
    if not isinstance(d, dict):
        return d
    for k in ("title", "dek", "uncertainty_note"):
        if k in d: d[k] = _s(d[k])
    for s in d.get("sections", []):
        s["heading"] = _s(s.get("heading"))
        for p in s.get("paras", []):
            p["t"] = _s(p.get("t"))
    r = d.get("reflection", {})
    for k in ("type", "scenario", "question"):
        if k in r: r[k] = _s(r[k])
    for k, v in list(r.get("example", {}).items()):
        r["example"][k] = _s(v)
    return d


def merge(zh, en):
    zh, en = _normalise(zh), _normalise(en)
    o = {"title": {"zh": zh["title"], "en": en.get("title", "")}, "dek": {"zh": zh["dek"], "en": en.get("dek", "")}, "sections": []}
    ens = {s["id"]: s for s in en.get("sections", [])}
    for s in zh["sections"]:
        e = ens.get(s["id"], {"heading": "", "paras": []})
        o["sections"].append({"id": s["id"], "heading": {"zh": s["heading"], "en": e.get("heading", "")},
                              "paras": [{"zh": p["t"], "en": (e["paras"][i].get("t", "") if i < len(e["paras"]) else ""),
                                         "kind": p["kind"], "ev": p.get("ev", [])} for i, p in enumerate(s["paras"])]})
    rz, re_ = zh["reflection"], en.get("reflection", {})
    o["reflection"] = {"type": rz["type"], **{k: {"zh": rz[k], "en": re_.get(k, "")} for k in ("scenario", "question")},
                       "example": {k: {"zh": rz["example"][k], "en": re_.get("example", {}).get(k, "")} for k in ("assumptions", "steps", "alternative")}}
    o["uncertainty_note"] = {"zh": zh["uncertainty_note"], "en": en.get("uncertainty_note", "")}
    return o


def run_model_steps(c, pack, outdir: Path, call=llm.call, timeouts=None) -> tuple[dict | None, dict | None, dict | None, list]:
    cfg = load_project().get("hermes", {}); t = timeouts or cfg.get("timeouts_s", {"draft_zh": 1800, "review_zh": 1200, "en": 2100})
    ev = _evidence_block(pack); metrics = []
    style = (PROMPTS / "style_zh.md").read_text(encoding="utf-8")

    def step(name, prompt, timeout, retry_suffix, validate):
        saved = outdir / f"{name}.json"
        if saved.exists() and not validate(json.loads(saved.read_text(encoding="utf-8"))):   # resume: reuse only a valid saved step
            metrics.append({"step": name, "candidate": c["candidate_id"], "reused": True, "json_ok": True, "wall_s": 0.0})
            return json.loads(saved.read_text(encoding="utf-8"))
        for attempt in (1, 2):
            r = call(prompt if attempt == 1 else prompt + retry_suffix, timeout_s=timeout)
            m = {k: v for k, v in r.items() if k != "text"}; m.update(step=name, attempt=attempt, candidate=c["candidate_id"])
            (outdir / f"{name}.a{attempt}.raw.txt").write_text(r["text"], encoding="utf-8")
            try:
                obj = llm.parse_json(r["text"]) if r["rc"] == 0 and not r["killed"] else None
            except ValueError:
                obj = None
            m["json_ok"] = obj is not None
            txt = r["text"].strip()
            if obj is None and len(txt) < 400 and REFUSAL.search(txt):
                m["provider_refusal"] = txt[:200]
            if obj is not None:                       # parseable is not enough: the step's schema must hold
                bad = validate(obj); m["schema_ok"] = not bad
                if bad:
                    m["schema_problems"] = bad[:5]; obj = None
                    retry_suffix = retry_suffix + "\n[Schema problems: " + "; ".join(bad[:5]) + "]"
            with open(outdir / "calls.jsonl", "a", encoding="utf-8") as log:      # append-only, after parsing: survives reruns
                log.write(json.dumps(dict(m, at=time.time()), ensure_ascii=False) + "\n")
            metrics.append(m)
            if "provider_refusal" in m:
                return None          # a content refusal will not change on retry
            if obj is not None:
                (outdir / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
                return obj
            if r["killed"] == "timeout":
                return None          # do not burn another full timeout
        return None

    zh = step("draft_zh", f"{style}\n\n{(PROMPTS/'draft_zh_long.md').read_text()}\n\n【编辑简报】\n{c['brief']}\n\n【证据包】\n{ev}",
              t["draft_zh"], "\n\n[上一次输出不是合法 JSON。只输出一个合法 JSON 对象。]", schemas.draft_zh)
    if zh is None:
        return None, None, None, metrics
    review = step("review_zh", f"{(PROMPTS/'review_zh.md').read_text()}\n\n【证据包】\n{ev}\n\n【稿件】\n{json.dumps(zh, ensure_ascii=False)}",
                  t["review_zh"], "\n\n[只输出一个合法 JSON 对象。]", schemas.review)
    en = step("en", f"{(PROMPTS/'translate_en_long.md').read_text()}\n\n{ev}\n\n<article_zh>\n{json.dumps(zh, ensure_ascii=False)}\n</article_zh>",
              t["en"], "\n\n[Reply with one valid JSON object only.]", schemas.draft_en)
    return zh, review, en, metrics


def prepare(c, db, *, call=llm.call, workdir: Path | None = None, cache: Path | None = None, drafter: str = "MiMo (hermes-isolated)",
            context_call=None) -> dict:
    """Run one candidate end to end. Returns a report dict; never raises for content problems.
    context_call: the reviewer for the pre-draft source-context step (context.review on the pack: how the episode ends
    in the source, additions cut from the reviewed text). Callers pass claude_cli.call; None skips it (tests). The
    article-mode review before admission is required either way."""
    cid = c["candidate_id"]; t0 = time.monotonic()
    out = Path(workdir or data_dir() / "drafts" / cid); out.mkdir(parents=True, exist_ok=True)
    cache = Path(cache or data_dir() / "source_cache"); cache.mkdir(parents=True, exist_ok=True)
    report = {"candidate_id": cid, "category": c["category"], "steps": [], "code_rev": CODE_REV, "drafter": drafter}

    def pend(reason, status="pending_review"):
        state.transition(db, cid, status, note=reason[:500], reason=reason[:2000]) if state.get(db, cid) is None or \
            status in state.ALLOWED.get(state.get(db, cid)["status"], set()) else None
        report.update(outcome=status, reason=reason, wall_s=round(time.monotonic() - t0, 1))
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        return report

    fetched = fetch_sources(c, cache)
    report["sources"] = {k: v.get("status") for k, v in fetched.items()}
    pack, errors = evidence.build(c["excerpts"], fetched, cache)
    (out / "evidence.json").write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding="utf-8")
    reasons = admission(c, fetched, pack, errors)
    if reasons:
        return pend("; ".join(reasons))
    ep = dict(c["episode"], spans=evidence.spans(pack, c.get("core_excerpts")), title=c.get("title_hint", cid), category=c["category"],
              episode_id=f"ep-{cid}")
    mine = db.execute("SELECT status FROM episode WHERE episode_id=?", (ep["episode_id"],)).fetchone()
    taken = db.execute("SELECT episode_id FROM episode WHERE episode_id!=? AND status IN ('reserved','prepared','checked','scheduled','published') "
                       "AND core_span=(SELECT core_span FROM episode WHERE episode_id=?)", (ep["episode_id"], ep["episode_id"])).fetchone() if mine else None
    if mine and mine[0] == "rejected" and taken:      # the span was taken by another edition since: duplicate, no model calls
        return pend(f"duplicate: core span now used by {taken[0]}", status="rejected")
    if mine:                                   # resumed after a crash: our own reservation, not a duplicate
        eid, verdict = ep["episode_id"], ("distinct", f"resumed own reservation ({mine[0]})")
    else:
        eid, verdict = registry.reserve(db, ep)
    report["dedup"] = verdict
    if verdict[0] == "duplicate":
        return pend(f"duplicate: {verdict[1]}", status="rejected")
    if verdict[0] == "review":
        return pend(f"possible duplicate: {verdict[1]}")
    report["episode_id"] = eid
    if context_call is not None:
        from . import context
        crec, cpack = context.review(None, pack, cache, out / "context", call=context_call, cid=cid)
        (out / "context_pre_draft.json").write_text(json.dumps(crec, ensure_ascii=False, indent=1), encoding="utf-8")
        report["context_pre_draft"] = {"outcome": crec.get("outcome"), "additions": [a["id"] for a in crec.get("additions") or []],
                                       "failure": crec.get("failure"), "elapsed_min": crec.get("elapsed_min")}
        if crec.get("outcome") == "prepared":
            pack = cpack; note = context.brief_note(crec)
            (out / "evidence.json").write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding="utf-8")
            if note:
                c = dict(c, brief=(c.get("brief") or "") + "\n" + note)
    zh, review, en, metrics = run_model_steps(c, pack, out, call=call)
    report["model_calls"] = metrics
    if zh is None or en is None:
        registry.set_status(db, eid, "rejected")
        refusals = [m for m in metrics if m.get("provider_refusal")]
        if refusals:
            return pend(f"provider refusal at {refusals[0]['step']}: {refusals[0]['provider_refusal']} (needs another model or an editor; do not reword to evade)")
        return pend("model step failed: " + ", ".join(f"{m['step']} rc={m.get('rc')} killed={m.get('killed')} json={m['json_ok']}" for m in metrics))
    obj = merge(zh, en)
    obj.update(schema_version="0.2", edition_id=cid, episode_id=eid, status="checked", edition_date=c.get("planned_date", "unscheduled"),
               category=c["category"], revision=1, correction_note=None, single_basis_disclosed=bool(c.get("single_basis_disclosed")),
               preheader=c.get("preheader", {"zh": obj["dek"]["zh"], "en": obj["dek"]["en"]}),
               sources=[{"id": sid, "citation": v["title"], "url": v.get("url"), "link_label": "source", "basis": v.get("basis")} for sid, v in pack["sources"].items()],
               further_reading=c.get("further_reading", []), episode={k: v for k, v in ep.items() if k not in ("title", "category")})
    for s in obj["sections"]:          # modern scenes cannot quote history: 「」 there is emphasis, not quotation
        for para in s["paras"]:
            if para["kind"] == "modern":
                para["zh"] = para["zh"].replace("「", "“").replace("」", "”")
    for k in ("scenario", "question"):
        obj["reflection"][k]["zh"] = obj["reflection"][k]["zh"].replace("「", "“").replace("」", "”")
    for k in obj["reflection"]["example"]:
        obj["reflection"]["example"][k]["zh"] = obj["reflection"]["example"][k]["zh"].replace("「", "“").replace("」", "”")
    render.finalize(obj)
    findings, stats = checks.check(obj, pack)
    report.update(length=obj["length"], reading_minutes=obj["reading_minutes"], findings=findings)
    # The evidence review's "fix" findings were substantive in practice (reversed meanings, feints written as
    # real retreats, invented times), so anything above "note" sends the draft to the pending queue.
    blocking_review = schemas.review_issues(review) if review is not None else []      # typed issues + separate fact arrays
    (out / "article.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    state.transition(db, cid, "prepared", note="model draft assembled", episode_id=eid, category=c["category"], path=str(out / "article.json"))
    if checks.blocked(findings) or blocking_review or review is None:
        why = ("checker BLOCK; " if checks.blocked(findings) else "") + (f"{len(blocking_review)} review issues rated fix/block; " if blocking_review else "") + ("" if review is not None else next((f"provider refusal at review_zh: {m['provider_refusal']} (another reviewer model or a person must review; do not reword to evade)"
                                         for m in metrics if m.get("step") == "review_zh" and m.get("provider_refusal")),
                                        "review missing or invalid (schema)" if any(m.get("schema_problems") for m in metrics if m.get("step") == "review_zh") else "review missing"))
        state.transition(db, cid, "pending_review", note=why, reason=why)
        registry.set_status(db, eid, "prepared")
        report.update(outcome="pending_review", reason=why, wall_s=round(time.monotonic() - t0, 1))
    else:                                   # clean drafts still need the editor stage: post-assembly re-review + English parity
        why = "awaiting editor stage: no blocking issues, final content and English not yet re-reviewed"
        state.transition(db, cid, "pending_review", note=why, reason=why)
        registry.set_status(db, eid, "prepared")
        report.update(outcome="pending_review", reason=why, wall_s=round(time.monotonic() - t0, 1))
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def _schedulable(approval, origin) -> bool:
    """Python mirror of state.SCHEDULABLE_SQL."""
    return bool(approval) and ((origin or "pipeline") != "sample" or str(approval).startswith("sample-approved"))


def rotation_days(counts: dict, rot: list, start: str) -> list[str]:
    """The categories the rotation fills, day by day from `start`, until a category runs out.
    The single coverage calculation: `hip inventory` and the report's what-if scenarios both use it."""
    i0 = rot.index(start) if start in rot else 0
    left, seq = dict(counts), []
    while len(seq) < 366 and left.get(rot[(i0 + len(seq)) % len(rot)], 0) > 0:
        c = rot[(i0 + len(seq)) % len(rot)]; left[c] -= 1; seq.append(c)
    return seq


def inventory(db, today: str | None = None) -> dict:
    """Inventory as the rotation will consume it. Only approved `checked` editions count toward coverage;
    samples need an explicit sample approval; pending drafts and unprocessed candidates are listed, never counted."""
    from .publish import next_category, today_la, IN_FLIGHT
    cfg = load_project(); rot = cfg.get("rotation", []); inv = cfg.get("inventory", {})
    target, alert_below = inv.get("target_days", 14), inv.get("alert_below_days", 7)
    today = today or today_la()
    rows = db.execute("SELECT edition_id, category, status, approval, origin, edition_date FROM edition").fetchall()
    ok = {c: 0 for c in rot}; awaiting = {c: 0 for c in rot}; samples = {"total": 0, "approved": 0}
    for eid, cat, st, appr, origin, d in rows:
        if (origin or ("sample" if eid.startswith("sample-") else "pipeline")) == "sample" and st == "checked":
            samples["total"] += 1; samples["approved"] += _schedulable(appr, "sample")
        if st == "checked" and cat in ok:
            if _schedulable(appr, origin):
                ok[cat] += 1
            else:
                awaiting[cat] += 1
    future = sorted(d for _, _, st, _, _, d in rows if st in IN_FLIGHT and d and d >= today)
    start = next_category(db); i0 = rot.index(start) if start in rot else 0
    seq = rotation_days(ok, rot, start)
    need = {c: 0 for c in rot}
    for k in range(max(0, target - len(future))):
        need[rot[(i0 + k) % len(rot)]] += 1
    gaps = {c: max(0, need[c] - ok[c]) for c in rot}
    cov = len(future) + len(seq)
    cands = sum(1 for p in (REPO / "config/candidates").glob("*.json")
                if not db.execute("SELECT 1 FROM edition WHERE edition_id=?", (json.loads(p.read_text(encoding="utf-8")).get("candidate_id"),)).fetchone())
    return {"coverage_days": cov, "target_days": target, "alert": cov < alert_below, "next_category": start,
            "scheduled_ahead": len(future), "coverage_sequence": seq[:target],
            "schedulable_by_category": ok, "schedulable_total": sum(ok.values()),
            "awaiting_approval_by_category": {c: n for c, n in awaiting.items() if n},
            "samples": samples, "gaps_to_target": {c: n for c, n in gaps.items() if n},
            "missing_categories": [c for c in rot if not ok[c]],
            "pending": db.execute("SELECT count(*) FROM edition WHERE status='pending_review'").fetchone()[0],
            "candidates_unprocessed": cands,
            "basis": "coverage = consecutive days the rotation can fill from next_category with approved checked editions, plus editions already scheduled ahead"}

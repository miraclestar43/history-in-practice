"""Automated supply: candidate -> sources -> evidence -> admission -> registry
-> Hermes (zh draft, evidence review, natural English) -> assemble -> checks ->
inventory (`checked`) or pending queue (`pending_review`, with reasons).

Default is automatic; nothing here waits for a human. Exceptions go to the
pending queue and other candidates continue. Automated `checked` means "passed
the deterministic checks and the model review with no blocking issue", which
is weaker than editor-reviewed; reports say so explicitly.
"""
from __future__ import annotations
import json, time
from pathlib import Path
from . import sources as src_mod, evidence, registry, render, checks, llm, state
from .config import REPO, data_dir, load_project

PROMPTS = Path(__file__).with_name("prompts")
import re as _re
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

    def step(name, prompt, timeout, retry_suffix):
        saved = outdir / f"{name}.json"
        if saved.exists():          # resume after a crash: never re-call the model for a step already done
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
                m["provider_refusal"] = txt[:200]; metrics.append(m)
                return None          # a content refusal will not change on retry
            metrics.append(m)
            if obj is not None:
                (outdir / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
                return obj
            if r["killed"] == "timeout":
                return None          # do not burn another full timeout
        return None

    zh = step("draft_zh", f"{style}\n\n{(PROMPTS/'draft_zh_long.md').read_text()}\n\n【编辑简报】\n{c['brief']}\n\n【证据包】\n{ev}",
              t["draft_zh"], "\n\n[上一次输出不是合法 JSON。只输出一个合法 JSON 对象。]")
    if zh is None:
        return None, None, None, metrics
    review = step("review_zh", f"{(PROMPTS/'review_zh.md').read_text()}\n\n【证据包】\n{ev}\n\n【稿件】\n{json.dumps(zh, ensure_ascii=False)}",
                  t["review_zh"], "\n\n[只输出一个合法 JSON 对象。]")
    en = step("en", f"{(PROMPTS/'translate_en_long.md').read_text()}\n\n{ev}\n\n<article_zh>\n{json.dumps(zh, ensure_ascii=False)}\n</article_zh>",
              t["en"], "\n\n[Reply with one valid JSON object only.]")
    return zh, review, en, metrics


def prepare(c, db, *, call=llm.call, workdir: Path | None = None, cache: Path | None = None) -> dict:
    """Run one candidate end to end. Returns a report dict; never raises for content problems."""
    cid = c["candidate_id"]; t0 = time.monotonic()
    out = Path(workdir or data_dir() / "drafts" / cid); out.mkdir(parents=True, exist_ok=True)
    cache = Path(cache or data_dir() / "source_cache"); cache.mkdir(parents=True, exist_ok=True)
    report = {"candidate_id": cid, "category": c["category"], "steps": []}

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
    blocking_review = [i for i in (review or {}).get("issues", []) if i.get("severity") in ("block", "fix")]
    (out / "article.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    state.transition(db, cid, "prepared", note="model draft assembled", episode_id=eid, category=c["category"], path=str(out / "article.json"))
    if checks.blocked(findings) or blocking_review or review is None:
        why = ("checker BLOCK; " if checks.blocked(findings) else "") + (f"{len(blocking_review)} review issues rated fix/block; " if blocking_review else "") + ("review missing" if review is None else "")
        state.transition(db, cid, "pending_review", note=why, reason=why)
        registry.set_status(db, eid, "prepared")
        report.update(outcome="pending_review", reason=why, wall_s=round(time.monotonic() - t0, 1))
    else:
        state.transition(db, cid, "checked", note="automated gates passed", content_sha256=obj["content_sha256"])
        registry.set_status(db, eid, "checked")
        report.update(outcome="checked", wall_s=round(time.monotonic() - t0, 1))
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def inventory(db) -> dict:
    rows = db.execute("SELECT category, count(*) FROM edition WHERE status IN ('checked','scheduled') GROUP BY category").fetchall()
    cats = dict(rows); total = sum(cats.values()); cfg = load_project().get("inventory", {})
    return {"by_category": cats, "days": total, "target_days": cfg.get("target_days", 14),
            "alert": total < cfg.get("alert_below_days", 7),
            "missing_categories": [k for k in load_project().get("rotation", []) if not cats.get(k)],
            "pending": db.execute("SELECT count(*) FROM edition WHERE status='pending_review'").fetchone()[0]}

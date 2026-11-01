"""Candidate supply: source catalogue -> fetched text window -> model proposal
(episode, 15–25 anchored excerpts, brief) -> mechanical validation -> dedup ->
config/candidates/auto-*.json, with provenance. Rejections are logged with
reasons in data/supply/attempts.jsonl.

What is mechanical (never trusted to the model): every excerpt anchor must
occur exactly once in the normalised source text and cut a bounded span;
excerpts overlapping spans already used by registered episodes are dropped;
the core excerpts must survive; the episode must pass the registry check.
The model's brief may only cite surviving excerpt ids; ids of dropped
excerpts are listed in the brief as unusable.
"""
from __future__ import annotations
import json, re, time
from pathlib import Path
from . import evidence, llm, registry, sources as src_mod
from .config import REPO, data_dir, load_project
from .pipeline import PROMPTS, REFUSAL, CODE_REV, fetch_sources, load_prompt

CATALOGUE = REPO / "config/source_catalogue.json"
MIN_EXCERPTS = 12
MAX_WINDOW = {True: 16000, False: 45000}       # characters handed to the model (CJK / other)
MAX_SPAN = {True: 900, False: 2500}


def load_catalogue() -> list[dict]:
    return json.loads(CATALOGUE.read_text(encoding="utf-8"))["entries"]


def source_spec(entry: dict) -> dict:
    sid = entry.get("cache_id") or f"S-{entry['id']}"
    return {"id": sid, "adapter": entry["adapter"], "ref": entry["ref"], "title": entry["title"], "basis": entry["basis"],
            "cjk": entry.get("cjk", False), "must_contain": entry.get("must_contain", [])}


def window(entry: dict, cache: Path) -> tuple[str, str, bool, dict]:
    """Normalised text the model sees, the full normalised text, cjk flag and fetch result."""
    spec = source_spec(entry); fetched = fetch_sources({"sources": [spec]}, cache)[spec["id"]]
    if fetched.get("status") != "evidence_usable":
        return "", "", spec["cjk"], fetched
    full = evidence.normalise((cache / f"{spec['id']}.txt").read_text(encoding="utf-8"), spec["cjk"])
    text = full
    if entry.get("window"):
        a, b = entry["window"]; i = full.find(a); j = full.find(b, i + 1)
        if i >= 0 and j > i:
            text = full[i:j]
    return text[:MAX_WINDOW[spec["cjk"]]], full, spec["cjk"], fetched


def used_spans(db, ref: str) -> list[tuple[int, int]]:
    out = []
    for (sp,) in db.execute("SELECT spans FROM episode WHERE status NOT IN ('rejected')"):
        out += [(a, b) for r, a, b in json.loads(sp) if r == ref]
    return out


def validate(prop: dict, full: str, cjk: bool, sid: str, prefix: str, taken: list[tuple[int, int]]) -> tuple[list, list]:
    """Mechanical anchor checks. Returns (excerpt spec rows, dropped [{id, reason}])."""
    rows, dropped, spans = [], [], []
    min_start = 10 if cjk else 25
    for e in prop.get("excerpts") or []:
        eid, a, b = str(e.get("id", "")), evidence.normalise(str(e.get("start", "")), cjk), evidence.normalise(str(e.get("end", "")), cjk)
        why = None
        if not re.fullmatch(r"E\d+", eid):
            why = "bad id"
        elif len(a) < min_start or len(b) < (4 if cjk else 10):
            why = "anchor too short"
        elif full.count(a) != 1:
            why = f"start anchor occurs {full.count(a)} times"
        else:
            i = full.find(a); j = full.find(b, i + len(a) - len(b))
            if j < 0 or j - i > MAX_SPAN[cjk]:
                why = "end anchor not found within limit"
            elif any(i < y and x < j + len(b) for x, y in spans):
                why = "overlaps another excerpt"
            elif any(i < y and x < j + len(b) for x, y in taken):
                why = "overlaps a passage used by a registered episode"
            else:
                spans.append((i, j + len(b)))
        if why:
            dropped.append({"id": eid, "reason": why}); continue
        rows.append([f"{prefix}-{eid}", sid, a, b, str(e.get("label", ""))[:60]])
    return rows, dropped


def _log(rec: dict):
    d = data_dir() / "supply"; d.mkdir(parents=True, exist_ok=True)
    with open(d / "attempts.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def attempts() -> list[dict]:
    p = data_dir() / "supply" / "attempts.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


# Theme tags (owner, 2026-10-30): breadth across the four rotation slots; war is one theme among many, no quota.
TAGS = ("历史", "政治与治理", "外交", "经济与金融", "企业与商业", "科学与技术", "人物传记", "社会与日常生活", "教育", "文化", "战争与冲突")


def pick_entry(category: str) -> dict | None:
    tried = {}
    for a in attempts():
        tried[a.get("catalogue_id")] = tried.get(a.get("catalogue_id"), 0) + 1
    pool = [e for e in load_catalogue() if e["category"] == category]
    return min(pool, key=lambda e: tried.get(e["id"], 0)) if pool else None


def propose(entry: dict, db, *, call=None, cache: Path | None = None, date: str | None = None, out_dir: Path | None = None) -> dict:
    """One proposal attempt for one catalogue entry. Writes a candidate file on success."""
    cache = Path(cache or data_dir() / "source_cache"); cache.mkdir(parents=True, exist_ok=True)
    date = date or time.strftime("%Y%m%d"); t0 = time.monotonic()
    rec = {"at": time.time(), "catalogue_id": entry["id"], "category": entry["category"], "code_rev": CODE_REV}
    from . import writer
    call = call or writer.call
    if call is writer.call and writer.preflight():           # no other model: stop, the caller reports health
        rec.update(outcome="not_run", health=True, reason="writer unavailable (Claude): " + "; ".join(writer.preflight())); return rec
    text, full, cjk, fetched = window(entry, cache)
    if not text:
        rec.update(outcome="rejected", reason=f"source not usable: {fetched.get('status')}"); _log(rec); return rec
    spec = source_spec(entry); taken = used_spans(db, spec["ref"])
    used_titles = [r[0] for r in db.execute("SELECT title FROM episode WHERE status NOT IN ('rejected')")]
    used_text = "\n".join(f"- {full[a:a + (60 if cjk else 160)]}……" for a, _ in sorted(taken)[:40]) or "（无）"
    prompt = (f"{load_prompt('propose_candidate')}\n\n类别：{entry['category']}\n"
              f"【已用过的段落（开头）】\n{used_text}\n\n【已有选题标题】\n" + "\n".join(f"- {t}" for t in used_titles[-60:]) +
              f"\n\n【原文】（{entry['title']}）\n<source>\n{text}\n</source>")
    r = call(prompt, timeout_s=1800); m = {k: v for k, v in r.items() if k != "text"}
    rec["call"] = {"wall_s": m["wall_s"], "rc": m["rc"], "killed": m["killed"], "prompt_bytes": m["prompt_bytes"], "out_bytes": m["out_bytes"]}
    rec["proposed_by"] = writer.name([m])
    try:
        prop = llm.parse_json(r["text"]) if r["rc"] == 0 and not r["killed"] else None
    except ValueError:
        prop = None
    if prop is None:
        refusal = len(r["text"].strip()) < 400 and REFUSAL.search(r["text"])
        rec.update(outcome="rejected", reason="provider refusal" if refusal else "no usable JSON from model", raw=r["text"][:300]); _log(rec); return rec
    pdir = data_dir() / "supply" / "proposals"; pdir.mkdir(parents=True, exist_ok=True)       # every proposal kept for audit
    ppath = pdir / f"{time.strftime('%Y%m%dT%H%M%S')}-{entry['id']}.json"
    ppath.write_text(json.dumps(prop, ensure_ascii=False, indent=1), encoding="utf-8"); rec["proposal_file"] = str(ppath)
    slug = re.sub(r"[^a-z0-9]+", "-", entry["id"].lower()).strip("-")
    n = 1 + sum(1 for p in (REPO / "config/candidates").glob(f"auto-*-{slug}-*.json"))
    cid = f"cand-auto-{date}-{slug}-{n}"; prefix = f"{slug.upper()}{n}"
    rows, dropped = validate(prop, full, cjk, spec["id"], prefix, taken)
    rec.update(candidate_id=cid, proposed=len(prop.get("excerpts") or []), kept=len(rows), dropped=dropped)
    core = [f"{prefix}-{c}" for c in (prop.get("core") or []) if f"{prefix}-{c}" in {x[0] for x in rows}]
    ep = prop.get("episode") or {}
    problems = []
    if len(rows) < MIN_EXCERPTS:
        problems.append(f"only {len(rows)} valid excerpts (need {MIN_EXCERPTS})")
    if not core:
        problems.append("no core excerpt survived validation")
    for k in ("persons", "year_from", "year_to", "place", "action"):
        if not ep.get(k) and ep.get(k) != 0:
            problems.append(f"episode.{k} missing")
    if not problems:
        pack, errs = evidence.build(rows, {spec["id"]: dict(fetched, ref=spec["ref"], title=spec["title"], basis=spec["basis"], cjk=cjk)}, cache)
        if errs:
            problems.append("evidence build: " + "; ".join(errs[:3]))
        else:
            v = registry.check(db, dict(ep, spans=evidence.spans(pack, core)))
            rec["dedup"] = v
            if v[0] != "distinct":
                problems.append(f"dedup {v[0]}: {v[1]}")
    if problems:
        rec.update(outcome="rejected", reason="; ".join(problems)); _log(rec); return rec
    brief = re.sub(r"\bE(\d+)\b", lambda mm: f"{prefix}-E{mm.group(1)}", str(prop.get("brief", "")))
    if dropped:
        # Lines that cite a dropped excerpt would hand the drafter facts with no evidence behind them
        # (seen in the first real run: 11 review issues traced to such lines). Remove those lines, keep a note.
        gone = {f"{prefix}-{d['id']}" for d in dropped}
        lines = brief.splitlines(); kept = [l for l in lines if not any(re.search(rf"{re.escape(g)}(?!\d)", l) for g in gone)]
        rec["brief_lines_removed"] = len(lines) - len(kept)
        brief = "\n".join(kept) + "\n注意：以下摘录的锚点未通过逐字核对，已删除；简报中引用它们的句子也已删除，不得写入相关内容：" + "、".join(sorted(gone)) + "。"
    cand = {"candidate_id": cid, "category": entry["category"], "title_hint": prop.get("title_hint", ""),
            "question_type": prop.get("question_type", ""), "single_basis_disclosed": True,
            "tags": [t for t in (prop.get("tags") or []) if t in TAGS][:3],
            "episode": {"persons": ep["persons"], "year_from": int(ep["year_from"]), "year_to": int(ep["year_to"]), "place": ep["place"],
                        "action": ep["action"], "parent_event": ep.get("parent_event")},
            "sources": [spec], "excerpts": rows, "core_excerpts": core, "brief": brief,
            "further_reading": [{"title": entry["title"], "url": entry.get("url"), "what": {"zh": "本篇依据的原文。", "en": "The source this piece is based on."},
                                 "access": {"zh": "免费在线" + ("，古文/繁体" if cjk else "，英文"), "en": "Free online" + (", classical Chinese" if cjk else ", English")}}],
            "preheader": prop.get("preheader") or {"zh": "", "en": ""},
            "provenance": {"proposed_by": f"{rec.get('proposed_by')} (prompts/propose_candidate.md)", "catalogue_id": entry["id"],
                           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "code_rev": CODE_REV,
                           "excerpts_proposed": rec["proposed"], "excerpts_dropped": dropped, "model_wall_s": m["wall_s"]}}
    out = Path(out_dir or REPO / "config/candidates"); out.mkdir(parents=True, exist_ok=True)
    path = out / f"auto-{date}-{entry['category']}-{slug}-{n}.json"
    path.write_text(json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
    rec.update(outcome="candidate", path=str(path), wall_s=round(time.monotonic() - t0, 1)); _log(rec)
    return rec


def check_catalogue(cache: Path | None = None) -> list[dict]:
    """Fetch every catalogue entry (cached) and report status and window size."""
    cache = Path(cache or data_dir() / "source_cache"); out = []
    for e in load_catalogue():
        text, full, cjk, fetched = window(e, cache)
        out.append({"id": e["id"], "category": e["category"], "status": fetched.get("status"), "window_chars": len(text), "full_chars": len(full)})
    return out

"""Source-context review: excerpts are read inside their source before drafting and again before admission.

Why: an evidence pack is a set of cut-outs. A decisive answer can sit just past a cut (吴起: 「魯君疑之，謝吳起」
right after excerpt E3), so an article can be consistent with every excerpt and still be wrong ("the source does
not record the ruler's response"). Hashes and verbatim checks only prove consistency with the chosen text.

Units (bounded, recorded): per cached source, the whole normalised text when it is short; otherwise windows
around every excerpt (more text after an excerpt than before, where outcomes are), merged, within a total cap.
A long source can get ONE bounded search round (terms the reviewer names, a few windows per term). Anything cut
by the cap is recorded as unreviewed; a source missing from the cache or changed since the evidence was cut is a
missing unit. Missing, truncated or unreviewed context never counts as verified absence.

Absence triage: absence_claims() flags sentences in every reader-visible field (zh and en) that look like
"the source does not say / 原文未载 / 没有交代 / unknown". It is triage only; the reviewer must also report claims it
finds itself, and the reviewer's verdict decides, with mechanical checks on top: every flagged sentence needs a
verdict; a contradiction needs a verbatim quote from the reviewed text; "supported" on a truncated or missing unit
becomes "unresolved"; quotes and addition anchors must occur in the reviewed spans.

Record (schema context-review/v1, mode pre_draft|article): source identity and cache text SHA-256, reviewed spans,
status per unit, flagged sentences, the reviewer's episode outcomes, additions actually cut, claim verdicts,
context issues, search terms and hits, blocking reasons, reviewer identity and calls. An article is admissible only
with an article-mode record that is clean and bound to its exact content and evidence (record_problems, used by
final_edit.admit and final_edit.current_eligibility). Expanding the evidence changes its hash, so any earlier
admission of that article stops verifying.
"""
from __future__ import annotations
import copy, hashlib, json, re, time
from pathlib import Path
from . import evidence, editor, claude_cli
from .config import data_dir, load_project
from .textnorm import t2s

SCHEMA = "context-review/v1"
PROMPT = Path(__file__).with_name("prompts") / "context_review.md"
_C = load_project().get("context_review", {})
WIN = {True: (_C.get("before_cjk", 1200), _C.get("after_cjk", 4000)), False: (_C.get("before_latin", 2500), _C.get("after_latin", 8000))}
CAP = {True: _C.get("cap_cjk", 60000), False: _C.get("cap_latin", 150000)}      # normalised chars per review, all sources together
SEARCH = {"terms": 6, "hits": 4, "win": {True: 1500, False: 3000}, "extra_cap": 0.3}
TIMEOUT = _C.get("timeout_s", 1500)
OK_VERDICTS = ("supported", "not_a_source_claim")
VERDICTS = ("supported", "contradicted", "unnecessary", "unresolved", "needs_search", "not_a_source_claim")
REVIEWER = {"name": "Pi Claude", "role": "named final editor (source-context review)", "runtime": "official Claude Code CLI on raspberrypi51"}

ZH_ABS = re.compile(r"(没有|沒有|未曾|并未|並未|不曾|未|无|無|只字未)(记载|記載|记录|記錄|写到|寫到|写明|寫明|写|寫|提到|提及|提|交代|說明|说明|说起|說|说|"
                    r"给出|給出|留下|讲|講|载|載|记|記)|不得而知|不详|不詳|未详|未詳|无从(得知|知道|知晓|判断|考证|查考)|止于|止於|只记|只記|只写|只寫|只说|只說|"
                    r"(?:没有|沒有|未经|未經|未获|未獲|缺少|缺乏|不存在|并无|並無)[^。！？\n]{0,40}"
                    r"(?:独立|獨立|第三方|外部|卫生部门|衛生部門)[^。！？\n]{0,24}(?:核查|核验|核驗|复核|複核|验证|驗證|审计|審計)")
EN_ABS = re.compile(r"\b(does|do|did)\s+not\s+(say|record|mention|explain|state|tell|give|report|describe|specify|indicate|note|show|survive|reveal|name)\b|"
                    r"\b(doesn't|don't|didn't)\s+(say|record|mention|explain|state|tell|give|report|describe|specify|name)\b|\bsilent\b|\bno record\b|"
                    r"\bnot recorded\b|\bunrecorded\b|\bnot known\b|\bunknown\b|\bwe (do not|don't|cannot|can't) know\b|\bnot stated\b|\bnowhere\b|"
                    r"\bstops (at|before|short)\b|\bonly (records|says|gives|mentions|notes|reports)\b|\bleaves? (it |this )?(open|unclear|unsaid)\b|"
                    r"\bno (account|mention|explanation)\b|\bwithout (saying|recording|explaining)\b|"
                    r"\b(?:no|without|lacks?|lacked|never)\b[^.!?\n]{0,80}\b(?:independent|external|third[- ]party|health authorit\w*)\b"
                    r"[^.!?\n]{0,45}\b(?:check\w*|verif\w*|audit\w*|review\w*|confirm\w*)\b", re.I)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sentences(text: str, lang: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；])" if lang == "zh" else r"(?<=[.!?;])\s+", text or "")
    return [p.strip() for p in parts if p.strip()]


def absence_claims(o: dict) -> list[dict]:
    """Triage: sentences that look like claims about what a source does not say (every visible field, both languages)."""
    out = []
    rows = [(p, zh, en) for p, zh, en in editor.fields(o)]
    for k, f in enumerate(o.get("further_reading") or []):
        for key in ("note", "why", "description", "what", "access"):
            v = f.get(key) if isinstance(f, dict) else None
            if isinstance(v, dict):
                rows.append((f"further_reading.{k}.{key}", v.get("zh", ""), v.get("en", "")))
    for path, zh, en in rows:
        for lang, text, rx in (("zh", zh, ZH_ABS), ("en", en, EN_ABS)):
            for s in _sentences(text, lang):
                if rx.search(s):
                    out.append({"id": f"A{len(out) + 1}", "path": path, "lang": lang, "sentence": s})
    return out


# ---------------------------------------------------------------- units

def _cjk(raw: str, ev: dict, sid: str) -> bool | None:
    """Which normalisation the pack's offsets refer to (None: offsets match neither -> text changed)."""
    exs = [e for e in ev["excerpts"] if e["source_id"] == sid]
    for cjk in (True, False):
        t = evidence.normalise(raw, cjk)
        if exs and all(t[e["offset"]:e["offset"] + len(e["quote"])] == e["quote"] for e in exs):
            return cjk
    return None


def _merge(spans):
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _allot(windows, rem):
    """Keep (a, b, centre) windows in order while the budget lasts; the first one that does not fit is trimmed around its
    centre (an excerpt start or a search hit: a little before it, the rest after), later ones are dropped."""
    kept, cut = [], []
    for a, b, c in windows:
        if b - a <= rem:
            kept.append([a, b]); rem -= b - a
        elif rem > 200:
            s = max(a, c - min(200, rem // 5)); kept.append([s, min(b, s + rem)]); cut.append([a, b]); rem = 0
        else:
            cut.append([a, b])
    return kept, cut, rem


def units(ev: dict, cache: Path, extra: dict | None = None) -> tuple[dict, dict]:
    """(meta, texts): meta is what the record keeps (no text); texts[sid] = (normalised text, cjk) for the reviewed spans.
    Excerpt windows share CAP (whole short sources come out of it first); search windows (extra) get their own
    SEARCH["extra_cap"] share. Anything trimmed or dropped is recorded under `unreviewed` and the unit is `truncated`."""
    meta, texts, plan = {}, {}, []
    for sid in sorted({e["source_id"] for e in ev["excerpts"]}):
        src = ev["sources"].get(sid, {}); p = Path(cache) / f"{sid}.txt"
        m = {"title": src.get("title"), "url": src.get("url"), "ref": src.get("ref"), "evidence_text_sha256": src.get("text_sha256")}
        if not p.exists():
            meta[sid] = dict(m, status="missing", why="not in the source cache"); continue
        raw = p.read_text(encoding="utf-8"); cjk = _cjk(raw, ev, sid)
        m["cache_sha256"] = _sha(p.read_bytes())
        if cjk is None:
            meta[sid] = dict(m, status="missing", why="cached text no longer matches the pack's excerpt offsets"); continue
        norm = evidence.normalise(raw, cjk); texts[sid] = (norm, cjk)
        m.update(cjk=cjk, source_chars=len(norm))
        if len(norm) <= CAP[cjk] * 0.5:                         # short source: the whole text is the unit
            meta[sid] = dict(m, status="complete", whole_source=True, spans=[[0, len(norm)]], chars_reviewed=len(norm)); continue
        meta[sid] = dict(m, status="windows", whole_source=False); plan.append(sid)
    budget = dict(CAP)
    for m in meta.values():
        if m.get("whole_source"):
            budget[m["cjk"]] -= m["source_chars"]
    xbudget = {k: int(v * SEARCH["extra_cap"]) for k, v in CAP.items()}
    for sid in plan:
        norm, cjk = texts[sid]; b0, a0 = WIN[cjk]
        exw = sorted((max(0, e["offset"] - b0), min(len(norm), e["offset"] + len(e["quote"]) + a0), e["offset"])
                     for e in ev["excerpts"] if e["source_id"] == sid)
        merged = []
        for a, b, c in exw:
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b, c])
        kept, cut, budget[cjk] = _allot(merged, budget[cjk])
        xs = [(a, b, (a + b) // 2) for a, b in (extra or {}).get(sid, [])]
        xk, xc, xbudget[cjk] = _allot(sorted(xs), xbudget[cjk])
        meta[sid]["spans"] = _merge(kept + xk); meta[sid]["chars_reviewed"] = sum(b - a for a, b in meta[sid]["spans"])
        if xs:
            meta[sid]["search_windows"] = len(xk)
        if cut or xc:
            meta[sid].update(status="truncated", unreviewed=cut + xc)
    return meta, texts


def render_units(meta: dict, texts: dict) -> str:
    out = []
    for sid, m in meta.items():
        head = f"〔{sid}〕{m.get('title') or ''}｜状态：{m['status']}"
        if m["status"] == "missing":
            out.append(f"{head}（{m.get('why')}；没有可读文本）"); continue
        norm, _ = texts[sid]
        head += f"｜全文 {m['source_chars']} 字符，" + ("本次阅读全文" if m.get("whole_source") else f"本次阅读 {len(m['spans'])} 段共 {m['chars_reviewed']} 字符")
        if m.get("unreviewed"):
            head += f"｜因篇幅上限未读 {len(m['unreviewed'])} 段（不能据此判断“没有记载”）"
        segs = [f"[{sid} {a}–{b}]\n{norm[a:b]}" for a, b in m["spans"]]
        out.append(head + "\n" + "\n…\n".join(segs))
    return "\n\n".join(out)


def search(texts: dict, meta: dict, terms: list[str]) -> tuple[dict, list]:
    """One bounded search round over windowed sources: a few windows around each hit of each named term."""
    extra, hits = {}, []
    for term in [t for t in terms if isinstance(t, str) and t.strip()][: SEARCH["terms"]]:
        for sid, (norm, cjk) in texts.items():
            if meta[sid].get("whole_source"):
                continue
            q = evidence.normalise(term, cjk); s = t2s(norm); simp = len(s) == len(norm)       # t2s keeps offsets only if length-preserving
            hay, needle = (s, t2s(q)) if simp else (norm, q)
            pos, n = 0, 0
            while n < SEARCH["hits"]:
                i = hay.find(needle, pos)
                if i < 0:
                    break
                w = SEARCH["win"][cjk]; extra.setdefault(sid, []).append([max(0, i - w), min(len(norm), i + len(q) + w)])
                hits.append({"term": term, "source_id": sid, "offset": i}); pos, n = i + 1, n + 1
    return extra, hits


# ---------------------------------------------------------------- checks on the reviewer's reply

def _canon(s: str, cjk: bool) -> str:
    s = evidence.normalise(str(s), cjk).strip("「」『』“”\"' ")
    return t2s(evidence.dehyphen(s))


def quote_in_units(q: dict, meta: dict, texts: dict) -> bool:
    sid = (q or {}).get("source_id"); s = (q or {}).get("quote", "")
    if sid not in texts or len(str(s).strip()) < 2:
        return False
    norm, cjk = texts[sid]; c = _canon(s, cjk)
    return len(c) >= 2 and any(c in _canon(norm[a:b], cjk) for a, b in meta[sid]["spans"])


def reply_schema(flagged: list, meta: dict, texts: dict, allow_search: bool):
    ids = {f["id"] for f in flagged}
    def v(obj):
        if not isinstance(obj, dict):
            return ["not a JSON object"]
        p = []
        # Missing fields are not a successful empty review. In particular, a detector miss
        # must not let {} become a clean record with no context review at all.
        for k in ("episode", "additions", "claims", "context_issues"):
            if k not in obj or not isinstance(obj[k], list):
                p.append(f"'{k}' is required and must be a list")
            elif any(not isinstance(item, dict) for item in obj[k]):
                p.append(f"'{k}' entries must be objects")
        if p:
            return p
        claim_ids = [c.get("id") for c in obj["claims"]]
        if any(not isinstance(i, str) or not i.strip() for i in claim_ids):
            return ["claim ids must be non-empty strings"]
        if len(set(claim_ids)) != len(claim_ids):
            p.append("duplicate claim ids")
        got = set(claim_ids)
        if ids - got:
            p.append(f"flagged claims without a verdict: {sorted(ids - got)[:6]}")
        for c in obj.get("claims", []):
            if not isinstance(c, dict) or c.get("verdict") not in VERDICTS:
                p.append(f"claim {c.get('id') if isinstance(c, dict) else c}: verdict must be one of {VERDICTS}"); continue
            if c["verdict"] == "needs_search" and not allow_search:
                p.append(f"claim {c['id']}: needs_search is not available in this round (use unresolved)")
            if c["verdict"] == "contradicted" and not quote_in_units(c.get("quote"), meta, texts):
                p.append(f"claim {c['id']}: contradicted needs a verbatim quote from the reviewed text")
            if c["verdict"] == "supported":
                source_ids = c.get("source_ids")
                if not (isinstance(c.get("scope"), str) and c["scope"].strip()
                        and isinstance(source_ids, list) and source_ids
                        and all(isinstance(s, str) and s in meta for s in source_ids)):
                    p.append(f"claim {c['id']}: supported needs scope and known source_ids")
        for i in obj.get("context_issues", []):
            if isinstance(i, dict) and i.get("severity") == "fix" and not quote_in_units(i.get("quote"), meta, texts):
                p.append(f"context issue at {i.get('path')}: needs a verbatim quote from the reviewed text")
        if allow_search and any(isinstance(c, dict) and c.get("verdict") == "needs_search" for c in obj.get("claims", [])) and not obj.get("search"):
            p.append("needs_search verdicts need search terms")
        return p
    return v


def apply_additions(ev: dict, adds: list, meta: dict, texts: dict) -> tuple[dict, list, list]:
    """Cut each requested addition from the reviewed spans (anchors verbatim) and append it to a copy of the pack."""
    new = copy.deepcopy(ev); done, failed = [], []
    for a in adds or []:
        sid = a.get("source_id") if isinstance(a, dict) else None
        if sid not in texts:
            failed.append({"addition": a, "error": "source not reviewed"}); continue
        norm, cjk = texts[sid]; s, e = evidence.normalise(str(a.get("start", "")), cjk), evidence.normalise(str(a.get("end", "")), cjk)
        hit = None
        for x, y in meta[sid]["spans"]:
            res, err = evidence.cut(norm[x:y], s, e) if s and e else (None, "empty anchor")
            if res:
                hit = (x + res[0], res[1]); break
        if not hit:
            failed.append({"addition": a, "error": "anchors not found in the reviewed text (or too long)"}); continue
        off, quote = hit
        if any(x["source_id"] == sid and x["offset"] <= off and off + len(quote) <= x["offset"] + len(x["quote"]) for x in new["excerpts"]):
            failed.append({"addition": a, "error": "already inside an existing excerpt"}); continue
        same = [x["id"] for x in new["excerpts"] if x["source_id"] == sid and re.match(r".+-E\d+$", x["id"])]
        prefix = same[0].rsplit("-E", 1)[0] if same else sid
        n = 1 + max([int(x["id"].rsplit("-E", 1)[1]) for x in new["excerpts"] if x["id"].startswith(prefix + "-E") and x["id"].rsplit("-E", 1)[1].isdigit()] or [0])
        ex = {"id": f"{prefix}-E{n}", "source_id": sid, "locator": f"context review addition: {str(a.get('why', ''))[:120]}", "offset": off,
              "start_anchor_hits": norm.count(s), "quote": quote, "display": evidence.dehyphen(quote), "added_by": "context review"}
        new["excerpts"].append(ex); done.append({"id": ex["id"], "source_id": sid, "offset": off, "chars": len(quote), "why": a.get("why")})
    return new, done, failed


# ---------------------------------------------------------------- the review

def review(o: dict | None, ev: dict, cache: Path, outdir: Path, *, call=None, cid: str = "") -> tuple[dict, dict]:
    """Run the review (o=None: pre-draft, on the pack only). Returns (record, evidence with additions)."""
    call = call or claude_cli.call; outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    mode = "article" if o is not None else "pre_draft"
    flagged = absence_claims(o) if o is not None else []
    t0 = time.time(); caller = editor.Caller(outdir, cid or (o or {}).get("edition_id", "pack"), call)
    meta, texts = units(ev, cache)
    rec = {"record_type": "context_review", "schema": SCHEMA, "mode": mode, "edition_id": (o or {}).get("edition_id") or cid,
           "content_sha256": (o or {}).get("content_sha256"), "evidence_in_sha256": editor.sha(ev),
           "reviewer": dict(REVIEWER, model=claude_cli.MODEL, cli_version=claude_cli.version() if call is claude_cli.call else "test-double"),
           "limits": {"window_cjk": WIN[True], "window_latin": WIN[False], "cap": CAP, "search": SEARCH}, "started_at": t0,
           "flagged": flagged, "search": None}
    if call is claude_cli.call:
        pre = claude_cli.preflight()
        if pre:
            return dict(rec, units=meta, outcome="not_run", failure="; ".join(pre), blocking=["context review not run: " + "; ".join(pre)]), ev
    art = (f"\n\n【稿件】\n{editor.article_view(o)}\n\n【待核断言】\n{json.dumps(flagged, ensure_ascii=False, indent=1)}" if o is not None
           else "\n\n（尚无稿件：只做 episode 与 additions；claims 与 context_issues 给空数组。）")
    from .pipeline import load_prompt
    tmpl = load_prompt(PROMPT.stem).replace("{稿件模式}", "" if o is not None else "（预备阶段无稿件，此项给空数组。）")
    def ask(step, allow_search):
        body = f"{tmpl}\n\n【阅读范围】\n{render_units(meta, texts)}\n\n【证据包】\n{json.dumps(ev['excerpts'], ensure_ascii=False)}{art}"
        return caller(step, body, TIMEOUT, "\n\n[Reply with one valid JSON object only, matching the schema.]",
                      validate=reply_schema(flagged, meta, texts, allow_search))
    has_windows = any(m["status"] in ("windows", "truncated") for m in meta.values())
    rep = ask("context_r1", has_windows)
    if rep is not None and has_windows and any(c.get("verdict") == "needs_search" for c in rep.get("claims", [])):
        extra, hits = search(texts, meta, rep.get("search") or [])
        rec["search"] = {"terms": (rep.get("search") or [])[: SEARCH["terms"]], "hits": hits}
        meta, texts = units(ev, cache, extra)
        rep = ask("context_r2", False)
    rec["units"] = meta
    rec["calls"] = [{k: m.get(k) for k in ("step", "attempt", "wall_s", "json_ok", "schema_ok", "schema_problems", "killed", "provider_refusal", "prompts")}
                    | {"output_tokens": ((m.get("meta") or {}).get("usage") or {}).get("output_tokens")} for m in caller.metrics]
    rec["finished_at"] = time.time(); rec["elapsed_min"] = round((rec["finished_at"] - t0) / 60, 1)
    if rep is None:
        m = caller.metrics[-1] if caller.metrics else {}
        why = str(m.get("provider_refusal") or (m.get("meta") or {}).get("error") or m.get("schema_problems") or m.get("killed") or "no usable JSON")[:300]
        return dict(rec, outcome="failed", failure=why, blocking=["context review failed: " + why], evidence_sha256=editor.sha(ev)), ev
    new_ev, added, failed = apply_additions(ev, rep.get("additions"), meta, texts)
    claims = []
    for c in rep.get("claims", []):
        c = dict(c); f = next((x for x in flagged if x["id"] == c.get("id")), None)
        if f:
            c.update(path=f["path"], lang=f["lang"], sentence=f["sentence"])        # the flagged text, not the model's echo
        if c["verdict"] == "needs_search":
            c.update(verdict="unresolved", downgraded="search round done; still needs context")
        bad = [s for s in c.get("source_ids") or [] if meta.get(s, {}).get("status") in ("missing", "truncated", None)]
        if c["verdict"] == "supported" and bad:
            c.update(verdict="unresolved", downgraded=f"unit {bad} missing or truncated: absence cannot be verified")
        c["unit_status"] = {s: meta.get(s, {}).get("status") for s in c.get("source_ids") or []}
        claims.append(c)
    blocking = [f"{c['path']}.{c.get('lang')}: {c['verdict']} — {str(c.get('sentence'))[:80]}" for c in claims if c["verdict"] not in OK_VERDICTS]
    blocking += [f"{i.get('path')}: {str(i.get('problem'))[:100]}" for i in rep.get("context_issues", []) if isinstance(i, dict) and i.get("severity") == "fix"]
    if mode == "article" and failed:
        blocking.append("context evidence additions failed: " + "; ".join(str(x) for x in failed)[:400])
    if mode == "article" and added:
        blocking.append(f"evidence must be expanded first: {len(added)} addition(s) {[a['id'] for a in added]}")
    rec.update(review=rep, claims=claims, context_issues=rep.get("context_issues", []), episode=rep.get("episode", []),
               additions=added, additions_failed=failed, evidence_sha256=editor.sha(new_ev),
               outcome="clean" if mode == "article" and not blocking else ("prepared" if mode == "pre_draft" else "needs_work"),
               blocking=blocking if mode == "article" else [])
    return rec, new_ev


def record_problems(rec: dict | None, o: dict, ev: dict, cache: Path | None = None) -> list[str]:
    """Admission gate: a clean article-mode review bound to this exact content and evidence, covering every
    flagged sentence, against source text that has not changed since."""
    if not rec:
        return ["no source-context review for this content"]
    if rec.get("schema") != SCHEMA or rec.get("mode") != "article":
        return ["not an article-mode context review of schema " + SCHEMA]
    p = []
    if rec.get("content_sha256") != o["content_sha256"]:
        p.append("context review is for different content")
    if rec.get("evidence_in_sha256") != editor.sha(ev) or rec.get("evidence_sha256") != editor.sha(ev):
        p.append("context review is for different evidence")
    if rec.get("outcome") != "clean":
        p.append(f"context review not clean: {'; '.join((rec.get('blocking') or [rec.get('failure') or rec.get('outcome')])[:3])}")
    ok = {(c.get("path"), c.get("lang"), c.get("sentence")) for c in rec.get("claims") or [] if c.get("verdict") in OK_VERDICTS}
    for f in absence_claims(o):
        if (f["path"], f["lang"], f["sentence"]) not in ok:
            p.append(f"absence-type sentence without an accepted verdict: {f['path']}.{f['lang']} {f['sentence'][:60]}")
    cache = Path(cache or data_dir() / "source_cache")
    for sid, m in (rec.get("units") or {}).items():
        f = cache / f"{sid}.txt"
        if m.get("status") == "missing":
            continue
        if not f.exists() or _sha(f.read_bytes()) != m.get("cache_sha256"):
            p.append(f"source {sid} changed or missing since the context review")
    return p


def issues_for_editor(rec: dict) -> list[dict]:
    """A non-clean review as issues the next final-editor attempt must handle (each with the reviewer's quote)."""
    out = []
    for c in rec.get("claims") or []:
        if c.get("verdict") in OK_VERDICTS:
            continue
        what = {"contradicted": "来源里其实有答案，必须按引文改写（不要改成“摘录未写”）",
                "unnecessary": "这句关于来源未载的断言没有必要，删去",
                "unresolved": "无法核实这句“未载”断言：删去，或改成只就已读范围准确表述的说法"}.get(c["verdict"], c["verdict"])
        q = c.get("quote") or {}
        out.append({"id": f"X{len(out) + 1}", "source": "context review", "where": c.get("path"),
                    "problem": f"来源上下文核查（{c.get('lang')}）「{c.get('sentence')}」：{what}" + (f"。来源原文〔{q.get('source_id')}〕：「{q.get('quote')}」" if q.get("quote") else ""),
                    "suggestion": c.get("fix")})
    for i in rec.get("context_issues") or []:
        if i.get("severity") != "fix":
            continue
        q = i.get("quote") or {}
        out.append({"id": f"X{len(out) + 1}", "source": "context review", "where": i.get("path"),
                    "problem": f"来源上下文核查：{i.get('problem')}" + (f"。来源原文〔{q.get('source_id')}〕：「{q.get('quote')}」" if q.get("quote") else ""),
                    "suggestion": None})
    if rec.get("additions"):
        out.append({"id": f"X{len(out) + 1}", "source": "context review", "where": "",
                    "problem": "证据包已按来源上下文补入摘录 " + ", ".join(a["id"] for a in rec["additions"]) + "；请据此检查叙事、结局与因果是否完整准确",
                    "suggestion": None})
    return out


def brief_note(rec: dict) -> str:
    """Pre-draft: what the drafter must know about how the episode ends in the source."""
    lines = [f"- {e.get('source_id')}：{e.get('outcome')}" + ("" if e.get("in_evidence") else "（结局原不在摘录中，已补入）") for e in rec.get("episode") or []]
    adds = ", ".join(a["id"] for a in rec.get("additions") or [])
    return ("【来源上下文】事件在来源中的收尾：\n" + "\n".join(lines) + (f"\n补入摘录：{adds}" if adds else "")) if lines or adds else ""

"""原文精选 (editor-in-chief 2026-11-02): an edition whose body is the author's own words.

The model chooses a continuous passage by paragraph number and says why; the PROGRAM extracts the text from the saved
book (never from the model's memory) and keeps its location. The model then writes only what is the editor's: a short
introduction, a few notes, a name list, an optional afterword and where to read on, and a paragraph-for-paragraph
translation into the other language, labelled as AI translation. A review reads the whole issue; its fixes may change
the editor's text and the translation, never the original. Mechanical checks: every displayed original paragraph is the
source paragraph byte for byte (and its normalised form is in the source cache), omissions are whole paragraphs marked
〔中略〕, the translation has one paragraph per original paragraph, every note's term is in its paragraph.

Records go to data/excerpts/<edition_id>/ (calls, raw replies, the object). The object (kind="excerpt") renders on the
web page and in the email next to the story editions (render.py).
"""
from __future__ import annotations
import hashlib, json, re, time
from pathlib import Path
from . import books, evidence, editor, render, state, registry
from .config import REPO, data_dir
from .library import get as lib_get, load as lib_load
from .pipeline import load_prompt

GAP = "〔中略〕"
TIMEOUT = {"select": 900, "guide": 900, "translate": 1800, "review": 1200}
MAX_WINDOW_CHARS = {True: 40000, False: 90000}


def book(book_id: str) -> tuple[dict, dict]:
    e = lib_get(lib_load(), book_id)
    f = next(x for x in json.loads((data_dir() / "books" / "manifest.json").read_text())["files"] if x["book_id"] == book_id)
    b = books.load(data_dir() / "books" / "files" / f["path"], e)
    if b["file_sha256"] != f["file_sha256"]:
        raise books.BookError(f"{book_id}: file changed since acquisition")
    return e, b


def numbered(b: dict, a: int, z: int) -> str:
    return "\n\n".join(f"[P{k}] {b['paragraphs'][k]['text']}" for k in range(a, z))


def chapter_heading(b: dict, k: int) -> str:
    """'CHAPTER XIII, MY INTERVIEWS WITH ...' when the chapter line is followed by a title line."""
    cs = [c for c in b.get("chapters") or [] if c["first_para"] <= k]
    if not cs:
        return ""
    c = cs[-1]; i = c["first_para"]
    nxt = b["paragraphs"][i + 1]["text"] if i + 1 < len(b["paragraphs"]) else ""
    return c["title"] + (f", {nxt}" if nxt.isupper() and len(nxt) < 90 else "")


MODERN_MARKS, CLASSICAL_MARKS = set("的了们这那么吗呢着"), set("之乎者也矣焉哉曰其於遂乃亦皆")
VERNACULAR_MIN = 30          # modern function words per 1,000 Chinese characters: 鲁迅/老残游记/叫魂 83-92, 晚清七十年 45,
                             # 李鸿章传 0.6, 浮生六记 0.5, 史记 0 (measured 2026-11-09). A screening hint, not a verdict
                             # (editor-in-chief 2026-11-09): below it a passage needs a recorded read-through finding it
                             # readable; books a reader confirmed classical (library register=classical) stay out.


def register(text: str) -> dict:
    """How modern a Chinese text reads, by the density of modern vs classical function words (per 1,000 characters)."""
    h = [c for c in text if "\u4e00" <= c <= "\u9fff"]; n = len(h) or 1
    return {"modern": round(1000 * sum(c in MODERN_MARKS for c in h) / n, 1), "classical": round(1000 * sum(c in CLASSICAL_MARKS for c in h) / n, 1),
            "chars": len(h)}


def vernacular_ok(text: str) -> bool:
    return register(text)["modern"] >= VERNACULAR_MIN


def is_heading(b: dict, k: int) -> bool:
    """A chapter heading line ('CHAPTER XII') or the upper-case chapter title right after it."""
    t = b["paragraphs"][k]["text"]
    if any(c["first_para"] == k for c in b.get("chapters") or []):
        return True
    return k > 0 and any(c["first_para"] == k - 1 for c in b.get("chapters") or []) and t.isupper() and len(t) < 90


# Gutenberg plain-text blocks that are not running text: picture markers, and footnote blocks ('[Footnote 3: ...]',
# '[28] Biographie Universelle.'). Left out of the passage without a 〔中略〕 mark; the body text is never touched.
NONTEXT = re.compile(r"^\[(Illustrations?[:\]. ]|Footnote \w+:|\d{1,3}\] )")


def is_nontext(b: dict, k: int) -> bool:
    return bool(NONTEXT.match(b["paragraphs"][k]["text"]))


def extract(b: dict, sel: dict) -> list[dict]:
    """The passage, from the saved book: paragraphs start..end, whole-paragraph omissions marked by gap_before."""
    a, z = int(sel["start"]), int(sel["end"])
    omit = {k for x, y in sel.get("omit") or [] for k in range(int(x), int(y) + 1)}
    if not (0 <= a <= z < len(b["paragraphs"])):
        raise ValueError(f"paragraph range {a}-{z} outside the book")
    if any(not (a < k < z) for k in omit):
        raise ValueError("an omission must lie strictly inside the passage")
    while a < z and is_heading(b, a):                 # chapter number / title lines are shown in the byline, not as text
        a += 1
    out, gap = [], False
    for k in range(a, z + 1):
        if k in omit:
            gap = True; continue
        if is_nontext(b, k):                          # a picture marker is not text and not an omission
            continue
        p = b["paragraphs"][k]
        out.append({"p": k, "orig": p["text"], "loc": p["loc"], "gap_before": gap}); gap = False
    return out


ZH_PART = 170                                         # display only: split long Chinese paragraphs near this length


def display_parts(text: str, target: int = ZH_PART) -> list[str] | None:
    """Phone-sized pieces of a long Chinese paragraph, cut only after a complete sentence (。！？… with any closing
    quote); the pieces join back to the paragraph exactly, so the paragraph stays the unit of correspondence."""
    if len(text) <= target * 1.4:
        return None
    sents = [s for s in re.findall(r".+?(?:[。！？…]+[”」』）]*|$)", text, flags=re.S) if s]
    parts, cur = [], ""
    for s in sents:
        if cur and len(cur) >= target * 0.6 and (len(cur) + len(s) > target or s.lstrip().startswith(("“", "「"))):
            parts.append(cur); cur = ""
        cur += s
    if cur:
        if parts and len(cur) < target * 0.35:
            parts[-1] += cur
        else:
            parts.append(cur)
    return parts if len(parts) > 1 and "".join(parts) == text else None


def add_display_parts(obj: dict) -> None:
    """Only for a Chinese AI translation: a Chinese original keeps the author's own paragraphing."""
    if obj["work"]["original_language"] == "zh":
        for x in obj["passage"]:
            x.pop("zh_parts", None)
        return
    for x in obj["passage"]:
        parts = display_parts(x["zh"])
        if parts:
            x["zh_parts"] = parts
        else:
            x.pop("zh_parts", None)


def passage_text(passage: list[dict]) -> str:
    return "\n\n".join((GAP + "\n\n" if x["gap_before"] else "") + f"[P{x['p']}] {x['orig']}" for x in passage)


def checks(obj: dict, b: dict, cache_text: str | None, cjk: bool) -> list[str]:
    """Mechanical: the original is the source, untouched; omissions are marked; translation aligned; notes anchored."""
    p = []
    lang = obj["work"]["original_language"]; tr = "en" if lang == "zh" else "zh"
    prev = None
    for x in obj["passage"]:
        src = b["paragraphs"][x["p"]]["text"]
        if x[lang] != src:
            p.append(f"P{x['p']}: displayed original differs from the source paragraph")
        if cache_text is not None and evidence.normalise(x[lang], cjk) not in cache_text:
            p.append(f"P{x['p']}: not found in the source cache")
        between = range(prev + 1, x["p"]) if prev is not None else range(0)
        if prev is not None and not x["gap_before"] and not all(is_nontext(b, k) for k in between):
            p.append(f"P{x['p']}: paragraphs skipped without a 〔中略〕 mark")
        if prev is not None and x["gap_before"] and all(is_nontext(b, k) for k in between):
            p.append(f"P{x['p']}: 〔中略〕 where nothing was left out")
        if not (x.get(tr) or "").strip():
            p.append(f"P{x['p']}: translation missing")
        mark = (b.get("img_mark") or "")
        if mark and mark in src:
            p.append(f"P{x['p']}: {src.count(mark)} character(s) are pictures in the source ({mark}); read them from the picture and record them before use")
        prev = x["p"]
    by = {x["p"]: x for x in obj["passage"]}
    for i, n in enumerate(obj.get("notes") or []):
        if n.get("para") not in by:
            p.append(f"note {i + 1}: paragraph P{n.get('para')} is not in the passage")
        elif n.get("term") and n["term"] not in by[n["para"]][lang]:
            p.append(f"note {i + 1}: term {n['term']!r} not in P{n['para']}")
    for x in obj["passage"]:
        if x.get("zh_parts") and "".join(x["zh_parts"]) != x["zh"]:
            p.append(f"P{x['p']}: display parts do not join back to the paragraph")
    shown = [obj.get("intro") or {}, obj.get("dek") or {}] + [{"zh": n.get("zh"), "en": n.get("en")} for n in obj.get("notes") or []]
    r = obj.get("reflect") or {}
    if r:
        shown += [r.get("angle") or {}, {"zh": " ".join(r["questions"]["zh"]), "en": " ".join(r["questions"]["en"])}]
    if any(re.search(r"(?<![A-Za-z])P\d{1,4}(?!\d)", str(t.get(k) or "")) for t in shown for k in ("zh", "en")):
        p.append("reader-facing editor text cites paragraph numbers (P12): readers do not see them")
    if lang == "zh":                                    # editor-in-chief 2026-11-08: a Chinese body must be modern vernacular;
        reg = register("".join(x["zh"] for x in obj["passage"]))   # 2026-11-09: the score screens, reading decides
        rd = obj.get("readability") or {}
        if rd.get("verdict") == "hard":
            p.append(f"a read-through found the Chinese body hard for a modern reader: {str(rd.get('reason') or '')[:120]}")
        elif reg["modern"] < VERNACULAR_MIN and not (rd.get("verdict") == "readable" and str(rd.get("reason") or "").strip()):
            p.append(f"few modern function words ({reg['modern']}/1000 < {VERNACULAR_MIN}): needs a recorded read-through "
                     "finding it readable modern Chinese before it can be used")
    for k in ("zh", "en"):
        if not (obj.get("intro") or {}).get(k):
            p.append(f"intro.{k} missing")
    return p


def _schema(kind: str, ids: list[int] | None = None):
    def v(o):
        if not isinstance(o, dict):
            return ["not a JSON object"]
        if kind == "select":
            if "skip" in o:
                return []
            return [f"{k} missing" for k in ("start", "end", "title", "why", "standalone") if k not in o]
        if kind == "guide":
            return [f"{k} missing" for k in ("dek", "intro", "names", "notes", "continue") if k not in o] + \
                   [f"{k}.zh/.en missing" for k in ("dek", "intro") if not (isinstance(o.get(k), dict) and o[k].get("zh") and o[k].get("en"))]
        if kind == "translate":
            got = [x.get("p") for x in o.get("paras") or [] if isinstance(x, dict)]
            return [] if got == ids and all((x.get("text") or "").strip() for x in o["paras"]) else [f"paragraphs {got} != {ids}"]
        if kind == "review":
            return [] if isinstance(o.get("issues"), list) else ["issues list missing"]
        return []
    return v


def _context(b: dict, a: int, n_chars: int = 9000) -> str:
    """The text just before the passage (what the reader has not seen), up to n_chars, whole paragraphs."""
    out, k, size = [], a - 1, 0
    while k >= 0 and size < n_chars:
        out.insert(0, f"[P{k}] {b['paragraphs'][k]['text']}"); size += len(b['paragraphs'][k]['text']); k -= 1
    return "\n\n".join(out)


def _toc(b: dict) -> str:
    return " / ".join(chapter_heading(b, c["first_para"]) for c in b.get("chapters") or [])


def run(book_id: str, window: tuple[int, int], edition_id: str, category: str, *, call=None, out_root: Path | None = None) -> dict:
    """One 原文精选 issue: select -> extract -> guide -> translate -> review (one fix round, then a check of the fixed
    fields) -> mechanical checks. Returns the object (and writes it with every record under data/excerpts/<id>/)."""
    e, b = book(book_id)
    cjk = e.get("language", "zh") == "zh"; lang = "zh" if cjk else "en"; other = "en" if cjk else "zh"
    out = Path(out_root or data_dir() / "excerpts") / edition_id; out.mkdir(parents=True, exist_ok=True)
    caller = editor.Caller(out, edition_id, call)
    meta = (f"【书目】{e.get('author')}《{e['title']}》；" + (f"本书正文是人工译文，译者：{e['translator']}（署名写作：{e.get('author')}{(e.get('role') or {}).get('zh') or '著'}，"
            f"{e['translator']}译；页面署名已按此显示）；" if e.get("translator") else "") + f"版本：{e.get('edition') or '见来源'}；原文语言：{'中文' if cjk else '英文'}；"
            f"性质：{e.get('genre')}；目录：{_toc(b)}")
    a, z = window
    if sum(len(b["paragraphs"][k]["text"]) for k in range(a, z)) > MAX_WINDOW_CHARS[cjk]:
        raise ValueError("window too long for one selection call")
    sel = caller("select", f"{load_prompt('excerpt_select')}\n\n{meta}\n\n【可选范围：第 P{a}–P{z - 1} 段】\n{numbered(b, a, z)}",
                 TIMEOUT["select"], "\n\n[Reply with one valid JSON object only.]", validate=_schema("select"))
    if sel is None or "skip" in sel:
        return {"outcome": "skipped" if sel else "failed", "reason": (sel or {}).get("skip") or "selection call failed"}
    passage = extract(b, sel)
    ptext = passage_text(passage)
    guide = caller("guide", f"{load_prompt('excerpt_guide')}\n\n{meta}\n\n【前文（读者没有读过）】\n{_context(b, int(sel['start']))}\n\n"
                            f"【选段】标题：{json.dumps(sel['title'], ensure_ascii=False)}\n{ptext}",
                   TIMEOUT["guide"], "\n\n[Reply with one valid JSON object only.]", validate=_schema("guide"))
    if guide is None:
        return {"outcome": "failed", "reason": "guide call failed"}
    ids = [x["p"] for x in passage]
    names = json.dumps(guide.get("names") or [], ensure_ascii=False)
    tr = caller("translate", f"{load_prompt('excerpt_translate')}\n\nTarget language: {'English' if other == 'en' else 'Chinese (简体中文)'}\n"
                             f"Names: {names}\nEditor's title: {json.dumps(sel['title'], ensure_ascii=False)}\n\n【Excerpt】\n{ptext}",
                TIMEOUT["translate"], "\n\n[Reply with one valid JSON object only, one entry per paragraph.]", validate=_schema("translate", ids))
    if tr is None:
        return {"outcome": "failed", "reason": "translation call failed"}
    for x, t in zip(passage, tr["paras"]):
        x[lang] = x.pop("orig"); x[other] = t["text"]
    obj = assemble(e, b, sel, guide, passage, edition_id, category)
    obj["review"] = []
    for rnd in (1, 2, 3):                               # fixes applied after rounds 1 and 2; round 3 only checks
        rv = caller(f"review_r{rnd}", f"{load_prompt('excerpt_review')}\n\n{meta}\n\n【前文】\n{_context(b, int(sel['start']))}\n\n"
                                      f"【本期】\n{json.dumps(view(obj), ensure_ascii=False, indent=1)}",
                    TIMEOUT["review"], "\n\n[Reply with one valid JSON object only.]", validate=_schema("review"))
        if rv is None:
            obj["review"].append({"round": rnd, "failed": True}); break
        fixes = [i for i in rv["issues"] if i.get("severity") == "fix"]
        applied = [apply_fix(obj, i) for i in fixes] if rnd < 3 else []
        obj["review"].append({"round": rnd, "reading": rv.get("reading"), "issues": rv["issues"], "applied": applied})
        if cjk and isinstance(rv.get("readability"), dict):   # the reviewer's read-through of the Chinese body
            obj["readability"] = {"verdict": rv["readability"].get("verdict"), "reason": rv["readability"].get("reason"),
                                  "by": "review", "round": rnd}
        if not any(applied):
            break
    obj["open_issues"] = [i for i in (obj["review"][-1].get("issues") or []) if i.get("severity") == "fix" and not i.get("_applied")]
    obj["episode_meta"] = guide.get("episode") or {}
    obj["calls"] = [{k: m.get(k) for k in ("step", "attempt", "wall_s", "json_ok", "schema_ok", "prompts")} | {"model": (m.get("meta") or {}).get("model")}
                    for m in caller.metrics]
    if not obj["open_issues"]:
        opened = obj["open_issues"]
        if reflect(obj, b, call=call, out=out) is None:
            obj["open_issues"] = opened + [{"id": "R0", "severity": "fix", "problem": "reflect step failed"}]
    add_display_parts(obj)
    cache = data_dir() / "source_cache" / f"{e.get('source_id')}.txt"
    obj["checks"] = checks(obj, b, evidence.normalise(cache.read_text(encoding="utf-8"), cjk) if cache.exists() else None, cjk)
    render.finalize(obj)
    (out / "excerpt.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return obj


def apply_fix(obj: dict, i: dict) -> bool:
    """A review fix may replace the editor's text (intro / notes / after / dek) or one translation paragraph; never the
    original. Selection-level problems are reported, not applied."""
    w, new = str(i.get("where") or ""), i.get("proposed")
    if not isinstance(new, str) or not new.strip() or is_xref(new):
        return False
    lang = obj["work"]["original_language"]; tr = "en" if lang == "zh" else "zh"
    m = re.fullmatch(r"title\.(zh|en)", w)
    if m:
        obj["title"][m.group(1)] = new; i["_applied"] = True; return True
    m = re.fullmatch(r"notes\.(\d+)\.label\.(zh|en)", w)
    if m and 0 < int(m.group(1)) <= len(obj["notes"]):
        obj["notes"][int(m.group(1)) - 1].setdefault("label", {})[m.group(2)] = new; i["_applied"] = True; return True
    m = re.fullmatch(r"(intro|after|dek)\.(zh|en)", w)
    if m and (obj.get(m.group(1)) or {}).get(m.group(2)) is not None:
        obj[m.group(1)][m.group(2)] = new; i["_applied"] = True; return True
    m = re.fullmatch(r"tr\.P(\d+)", w)
    if m and (obj.get("translation") or {}).get("human"):
        return False                                    # a published human translation is never rewritten (2026-11-10)
    if m:
        x = next((x for x in obj["passage"] if x["p"] == int(m.group(1))), None)
        if x:
            x[tr] = new; i["_applied"] = True; return True
    m = re.fullmatch(r"notes\.(\d+)(?:\.(zh|en))?", w)
    if m and 0 < int(m.group(1)) <= len(obj["notes"]):
        n = obj["notes"][int(m.group(1)) - 1]
        if m.group(2):
            n[m.group(2)] = new
        else:
            n["zh"] = new
        i["_applied"] = True; return True
    return False


def view(obj: dict) -> dict:
    lang = obj["work"]["original_language"]; tr = "en" if lang == "zh" else "zh"
    return {"title": obj["title"], "dek": obj["dek"], "intro": obj["intro"],
            "passage": [{"p": x["p"], "gap_before": x["gap_before"], "original": x[lang], "translation": x[tr]} for x in obj["passage"]],
            "notes": [{"n": i + 1, **n} for i, n in enumerate(obj["notes"])], "after": obj.get("after"), "continue": obj.get("continue")}


ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
CN = "零一二三四五六七八九"


def _roman(r: str) -> int | None:
    if not r or any(c not in ROMAN for c in r):
        return None
    n = 0
    for i, c in enumerate(r):
        v = ROMAN[c]; n += -v if i + 1 < len(r) and ROMAN[r[i + 1]] > v else v
    return n


def _cn(n: int) -> str:
    return CN[n] if n < 10 else ("十" if n < 20 else CN[n // 10] + "十") + (CN[n % 10] if n % 10 else "")


def chapter_labels(head: str) -> tuple[str, str]:
    """'CHAPTER XIII, MY INTERVIEWS WITH TSANG KWOH FAN' -> ('第十三章', 'Chapter XIII, “My Interviews with Tsang Kwoh Fan”')."""
    m = re.match(r"CHAPTER ([IVXLC]+)(?:, (.*))?$", head or "")
    if not m:                                           # a bare "CHAPTER" or a caption is no label at all
        ok = bool(head) and not re.fullmatch(r"(?i)chapter\.?|\W*", head or "") and len(head) < 60
        return (head, head) if ok else ("", "")
    n = _roman(m.group(1)); t = (m.group(2) or "").title().replace(" With ", " with ").replace(" To ", " to ").replace(" Of ", " of ").replace(" The ", " the ")
    return (f"第{_cn(n)}章" if n else head), f"Chapter {m.group(1)}" + (f", “{t}”" if t else "")


def assemble(e: dict, b: dict, sel: dict, guide: dict, passage: list[dict], edition_id: str, category: str) -> dict:
    lang = "zh" if e.get("language", "zh") == "zh" else "en"
    first, last = passage[0]["p"], passage[-1]["p"]
    head = chapter_heading(b, first); ch_zh, ch_en = chapter_labels(head)
    if e.get("piece_zh"):                               # one essay of a collection: the essay is the "chapter"
        ch_zh, ch_en, head = e["piece_zh"], e.get("piece_en") or e["piece_zh"], e["piece_zh"]
    pa = sel.get("passage_author") or {}                # the passage is by someone other than the book's author (an
    if pa.get("en") or pa.get("zh"):                    # introduction, a quoted letter): the byline names who wrote it
        e = dict(e, author_en=pa.get("en") or e.get("author_en"), author_zh=pa.get("zh") or e.get("author_zh"),
                 role={"zh": pa.get("role_zh") or "撰", "en": pa.get("role_en") or "author"})
    return {"kind": "excerpt", "schema_version": "excerpt/1", "edition_id": edition_id, "revision": 1, "category": category,
            "title": sel["title"], "title_note": {"zh": "编辑拟题", "en": "Title by the editor"},
            "dek": guide["dek"], "intro": guide["intro"], "preheader": guide["dek"],
            "work": {"book_id": e["book_id"], "author": e.get("author_en") or e.get("author"), "author_zh": e.get("author_zh") or e.get("author"),
                     "title": e["title"], "title_en": e.get("title_en"), "title_zh": e.get("title_zh"), "title_zh_note": e.get("title_zh_note"), "chapter_zh": ch_zh, "chapter_en": ch_en,
                     "rights_label": e.get("rights_label"), "edition": e.get("edition"), "role": e.get("role"),
                     "translator": e.get("translator"), "translator_en": e.get("translator_en"),
                     "original_language": lang, "chapter": head, "paragraphs": [first, last],
                     "location": f"{head}; paragraphs {first}–{last} of the edition's text" + (" (with omissions marked 〔中略〕)" if any(x["gap_before"] for x in passage) else ""),
                     "file_sha256": e.get("file_sha256"), "rights": e.get("rights"), "rights_note": e.get("rights_note"),
                     "reading_url": e.get("reading_url")},
            "translation": {"lang": "en" if lang == "zh" else "zh", "label": {"zh": "AI 译文", "en": "AI translation"},
                            "by": "Claude Opus (claude-opus-5-5) via Claude Code CLI"},
            "tags": list(e.get("themes") or [])[:3],
            "passage": passage, "names": guide.get("names") or [], "notes": guide.get("notes") or [],
            "after": guide.get("after"), "continue": guide.get("continue"),
            "selection": {k: sel.get(k) for k in ("start", "end", "omit", "why", "standalone", "context_needed", "omit_check")}}


# ------------------------------------------------------------------ paired reading: author's original + published human translation (2026-11-10)

def run_paired(src_id: str, tr_id: str, src_range: tuple[int, int], tr_range: tuple[int, int], edition_id: str, category: str, *,
               call=None, out_root: Path | None = None) -> dict:
    """A private bilingual reading piece: the author's original (src) and an existing human translation (tr) of the same
    passage, paragraph for paragraph, both taken verbatim from the two editions. The editor fixes the range; the
    program checks the pairing; the model writes title, why-read, guide, notes, review and questions, never the text."""
    es, bs = book(src_id); et, bt = book(tr_id)
    a, z = src_range; ta, tz = tr_range
    if z - a != tz - ta:
        raise ValueError("paired ranges must have the same number of paragraphs (one-to-one)")
    src_lang = "zh" if es.get("language", "zh") == "zh" else "en"; tr_lang = "en" if src_lang == "zh" else "zh"
    out = Path(out_root or data_dir() / "excerpts") / edition_id; out.mkdir(parents=True, exist_ok=True)
    caller = editor.Caller(out, edition_id, call)
    passage = [{"p": k, src_lang: bs["paragraphs"][k]["text"], tr_lang: bt["paragraphs"][k - a + ta]["text"], "tr_p": k - a + ta, "gap_before": False}
               for k in range(a, z)]
    pairing = pair_check(passage, src_lang, tr_lang)
    meta = (f"【书目】{es.get('author')}《{es['title']}》（原文，{es.get('edition')}）；中译：{et.get('author')}《{et['title']}》，"
            f"{et.get('translator')} 译，{et.get('edition')}。本期是给主人私人阅读的双语成品：英文是作者原文，中文是已出版的人工译本，"
            f"两者都按原书逐段照录，不得改写、不得重译；如发现某段中英不对应，只报告，不改文字。注释的中文入口词请用中译本里的原词。")
    tr_text = "\n\n".join(f"[P{x['p']}] {x[tr_lang]}" for x in passage)
    sel = caller("select", f"{load_prompt('excerpt_select')}\n\n{meta}\n\n【范围已由编辑定好：第 P{a}–P{z - 1} 段，请完整保留（start={a}, end={z - 1}, omit=[]），"
                           f"只需给出标题、选段理由（为什么值得主人读：它帮人理解什么经济、商业或个人选择）、能否独立成篇、需要的背景】\n{numbered(bs, a, z)}",
                 TIMEOUT["select"], "\n\n[Reply with one valid JSON object only.]", validate=_schema("select"))
    if sel is None or "skip" in sel:
        return {"outcome": "failed", "reason": (sel or {}).get("skip") or "selection call failed"}
    sel.update(start=a, end=z - 1, omit=[], range_fixed_by="editor (owner's request 2026-11-10)")
    ptext = "\n\n".join(f"[P{x['p']}] {x[src_lang]}" for x in passage)
    guide = caller("guide", f"{load_prompt('excerpt_guide')}\n\n{meta}\n\n【前文（读者没有读过）】\n{_context(bs, a)}\n\n"
                            f"【选段】标题：{json.dumps(sel['title'], ensure_ascii=False)}\n{ptext}\n\n【同一选段的已出版中译（逐段对应）】\n{tr_text}",
                   TIMEOUT["guide"], "\n\n[Reply with one valid JSON object only.]", validate=_schema("guide"))
    if guide is None:
        return {"outcome": "failed", "reason": "guide call failed"}
    obj = assemble(es, bs, sel, guide, passage, edition_id, category)
    obj["private"] = True
    obj["translation"] = {"lang": tr_lang, "human": True, "label": {"zh": "人工译文", "en": "published translation"},
                          "by": f"{et.get('translator')} 译 · {et.get('edition')}", "book_id": tr_id, "file_sha256": et.get("file_sha256"),
                          "paragraphs": [ta, tz - 1]}
    obj["work"]["translator"] = et.get("translator"); obj["work"]["translator_en"] = f"Chinese translation by {et.get('translator')}"
    obj["work"].update(paired_labels(es, bs, a, et, bt, ta))
    obj["pairing"] = pairing
    obj["review"] = []
    for rnd in (1, 2, 3):
        rv = caller(f"review_r{rnd}", f"{load_prompt('excerpt_review')}\n\n{meta}\n\n【前文】\n{_context(bs, a)}\n\n"
                                      f"【本期】\n{json.dumps(view(obj), ensure_ascii=False, indent=1)}",
                    TIMEOUT["review"], "\n\n[Reply with one valid JSON object only.]", validate=_schema("review"))
        if rv is None:
            obj["review"].append({"round": rnd, "failed": True}); break
        fixes = [i for i in rv["issues"] if i.get("severity") == "fix"]
        applied = [apply_fix(obj, i) for i in fixes] if rnd < 3 else []
        obj["review"].append({"round": rnd, "reading": rv.get("reading"), "issues": rv["issues"], "applied": applied})
        if not any(applied):
            break
    last = obj["review"][-1].get("issues") or []
    obj["open_issues"] = [i for i in last if i.get("severity") == "fix" and not i.get("_applied") and not str(i.get("where", "")).startswith("tr.P")]
    obj["translation_reports"] = [i for r in obj["review"] for i in (r.get("issues") or []) if str(i.get("where", "")).startswith("tr.P")]
    obj["calls"] = [{k: m.get(k) for k in ("step", "attempt", "wall_s", "json_ok", "schema_ok", "prompts")} | {"model": (m.get("meta") or {}).get("model")}
                    for m in caller.metrics]
    if not obj["open_issues"] and reflect(obj, bs, call=call, out=out) is None:
        obj["open_issues"] = [{"id": "R0", "severity": "fix", "problem": "reflect step failed"}]
    add_display_parts(obj)
    cache = data_dir() / "source_cache" / f"{es.get('source_id')}.txt"
    obj["checks"] = checks(obj, bs, evidence.normalise(cache.read_text(encoding="utf-8"), src_lang == "zh") if cache.exists() else None, src_lang == "zh")
    obj["checks"] += [f"P{x['p']}: displayed translation differs from paragraph {x['tr_p']} of the translation"
                      for x in passage if x[tr_lang] != bt["paragraphs"][x["tr_p"]]["text"]]
    obj["checks"] += [f"P{d['p']}: pairing doubtful ({d['why']})" for d in pairing["doubtful"]]
    render.finalize(obj)
    (out / "excerpt.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return obj


def paired_labels(es: dict, bs: dict, a: int, et: dict, bt: dict, ta: int) -> dict:
    """Book and chapter as each language's reader knows them: the Chinese edition's own title and chapter heading for
    the Chinese side, the original's for the English side ('第1章 风险投资' / 'Chapter 1: Venture')."""
    zh_ch = chapter_heading(bt, ta) if bt.get("chapters") else ""
    en_ch = chapter_heading(bs, a) if bs.get("chapters") else ""
    m = re.match(r"第(\d+)章", zh_ch or "")
    en_ch = ", ".join(dict.fromkeys(x.strip() for x in (en_ch or "").split(",") if x.strip()))     # 'VENTURE, VENTURE' -> 'VENTURE'
    en = en_ch.title() if en_ch.isupper() else en_ch
    return {"title_zh": et["title"] if et.get("language", "zh") == "zh" else es.get("title_zh"),
            "chapter_zh": zh_ch, "chapter_en": (f"Chapter {m.group(1)}: {en}" if m and en else en)}


ENDNOTE = re.compile(r"\[\d{1,4}\]")
_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
                                     "seventeen eighteen nineteen".split())} | {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
                                     "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "a": 1}


def spelled_numbers(text: str) -> set[str]:
    """'three thousand' -> '3000', 'twenty-five' -> '25', 'two hundred' -> '200' (enough to pair digits in a translation)."""
    out = set()
    for m in re.finditer(r"\b((?:[a-z]+[- ])*?[a-z]+)\s+(hundred|thousand|million)\b|\b([a-z]+)-([a-z]+)\b|\b([a-z]+)\b", text.lower()):
        if m.group(2):
            words = re.split(r"[- ]", m.group(1)); n = sum(_UNITS.get(w, 0) for w in words[-2:])
            if n: out.add(str(n * {"hundred": 100, "thousand": 1000, "million": 1000000}[m.group(2)]))
        elif m.group(3) and m.group(3) in _UNITS and m.group(4) in _UNITS:
            out.add(str(_UNITS[m.group(3)] + _UNITS[m.group(4)]))
        elif m.group(5) in _UNITS and m.group(5) != "a":
            out.add(str(_UNITS[m.group(5)]))
    return out


def pair_check(passage: list[dict], src: str, tr: str) -> dict:
    """Mechanical pairing check: numbers written as digits in the translation must be in the original (as digits, or
    written out there), names given in Latin letters in the translation must be in the original, and the length ratio
    must stay near the passage's median. Returns per-paragraph facts and the doubtful pairs."""
    rows, doubtful = [], []
    ratios = []
    for x in passage:
        o, t = x[src], ENDNOTE.sub("", x[tr])
        ratios.append(len(o) / max(1, len(t)))
    med = sorted(ratios)[len(ratios) // 2] if ratios else 1
    for x, r in zip(passage, ratios):
        o, t = x[src], ENDNOTE.sub("", x[tr])
        latin = [w for w in re.findall(r"[（(]([A-Za-z][A-Za-z .'’-]+)[）)]", t) if w.split()[-1] not in o]
        nums_t = {n.replace(",", "") for n in re.findall(r"\d[\d,]*", t)}; nums_o = {n.replace(",", "") for n in re.findall(r"\d[\d,]*", o)} | spelled_numbers(o)
        big = sorted(n for n in nums_t - nums_o if len(n) >= 3 and not (len(n) == 4 and n.startswith(("1", "2")) and n in o))
        row = {"p": x["p"], "tr_p": x["tr_p"], "ratio": round(r, 2), "latin_missing": latin, "numbers_only_in_translation": big}
        rows.append(row)
        why = []
        if not (0.6 * med <= r <= 1.6 * med): why.append(f"length ratio {r:.2f} vs median {med:.2f}")
        if latin: why.append(f"names not in the original: {latin}")
        if big: why.append(f"numbers not in the original: {big}")
        if why: doubtful.append((x, "; ".join(why)))
    return {"median_ratio": round(med, 2), "rows": rows, "doubtful": [{"p": x["p"], "why": w} for x, w in doubtful]}


# ------------------------------------------------------------------ after the text: 读后想一想 + 一个参考角度 (2026-11-02)

def reflect(obj: dict, b: dict, *, call=None, out: Path | None = None) -> dict | None:
    """One or two questions about the people, their choices or the writing, and one folded 'reference angle' that points
    at details of the text and offers one possible reading (with its limits). Editor's content, labelled as such; may
    be skipped when nothing is worth asking. Then a review of exactly these fields (basis, attribution, language)."""
    out = Path(out or data_dir() / "excerpts" / obj["edition_id"]); out.mkdir(parents=True, exist_ok=True)
    caller = editor.Caller(out, obj["edition_id"], call)
    lang = obj["work"]["original_language"]
    body = "\n\n".join(f"[P{x['p']}] {x[lang]}" for x in obj["passage"])
    ctx = json.dumps({"title": obj["title"], "intro": obj["intro"], "notes": obj["notes"]}, ensure_ascii=False)
    g = caller("reflect", f"{load_prompt('excerpt_reflect')}\n\n【本期标题、导读、注释】\n{ctx}\n\n【原文】\n{body}",
               TIMEOUT["guide"], "\n\n[Reply with one valid JSON object only.]", validate=_reflect_schema)
    if g is None:
        return None
    if "skip" in g:
        obj["reflect"] = None; obj.setdefault("review", []).append({"round": "reflect", "skipped": g["skip"]}); return obj
    obj["reflect"] = {"questions": g["questions"], "angle": g["angle"]}
    rv = caller("reflect_review", f"{load_prompt('excerpt_reflect_review')}\n\n【原文】\n{body}\n\n【导读】\n{json.dumps(obj['intro'], ensure_ascii=False)}\n\n"
                                  f"【读后想一想与参考角度】\n{json.dumps(obj['reflect'], ensure_ascii=False, indent=1)}",
                TIMEOUT["review"], "\n\n[Reply with one valid JSON object only.]", validate=_schema("review"))
    applied = []
    for i in (rv or {}).get("issues") or []:
        if i.get("severity") == "fix":
            applied.append(_apply_reflect_fix(obj, i))
    obj.setdefault("review", []).append({"round": "reflect", "reading": (rv or {}).get("reading"), "issues": (rv or {}).get("issues"),
                                         "applied": applied, "failed": rv is None})
    obj["open_issues"] = [i for i in (rv or {}).get("issues") or [] if i.get("severity") == "fix" and not i.get("_applied")] + \
                         ([{"id": "R0", "severity": "fix", "problem": "reflect review failed"}] if rv is None else [])
    obj["calls"] = (obj.get("calls") or []) + [{k: m.get(k) for k in ("step", "attempt", "wall_s", "json_ok", "schema_ok", "prompts")} |
                                               {"model": (m.get("meta") or {}).get("model")} for m in caller.metrics]
    return obj


def _reflect_schema(o):
    if not isinstance(o, dict):
        return ["not a JSON object"]
    if "skip" in o:
        return []
    q, a = o.get("questions"), o.get("angle")
    bad = []
    if not (isinstance(q, dict) and isinstance(q.get("zh"), list) and isinstance(q.get("en"), list) and 1 <= len(q["zh"]) <= 2 and len(q["zh"]) == len(q["en"])):
        bad.append("questions must be {zh:[1-2], en:[same count]}")
    if not (isinstance(a, dict) and a.get("zh") and a.get("en")):
        bad.append("angle.zh/.en missing")
    return bad


XREF = re.compile(r"^\s*(同|见|参见|参照|如|按)\s*[A-Z]+\d+|^\s*(same as|see)\s+[A-Z]+\d+", re.I)


def is_xref(new) -> bool:
    """A reviewer's 'proposed' that points at another fix ('同 Q3 修改后的 angle.zh 全文') instead of giving the text."""
    return isinstance(new, str) and bool(XREF.search(new))


def _apply_reflect_fix(obj: dict, i: dict) -> bool:
    w, new = str(i.get("where") or ""), i.get("proposed")
    if not isinstance(new, str) or not new.strip() or is_xref(new):
        return False
    m = re.fullmatch(r"angle\.(zh|en)", w)
    if m:
        obj["reflect"]["angle"][m.group(1)] = new; i["_applied"] = True; return True
    m = re.fullmatch(r"questions\.(zh|en)\.(\d+)", w)
    if m and int(m.group(2)) < len(obj["reflect"]["questions"][m.group(1)]):
        obj["reflect"]["questions"][m.group(1)][int(m.group(2))] = new; i["_applied"] = True; return True
    return False


# ------------------------------------------------------------------ admission (原文精选 into inventory)

ADMIT_ROOT = REPO / "samples" / "excerpts"            # admitted objects of public-domain texts are tracked in Git


def approval_of(obj: dict) -> str:
    models = sorted({c.get("model") for c in obj.get("calls") or [] if c.get("model")})
    return f"excerpt-editor: Claude ({', '.join(models) or 'model not reported'}) via Claude Code CLI; record {editor.sha(obj)[:12]}"


def record_problems(obj: dict, approval: str | None = None) -> list[str]:
    """Re-verify an admitted 原文精选 on this machine: the book file is the recorded edition, every displayed original
    paragraph is that file's paragraph, the translation and notes line up (checks), nothing is left open, every call
    reported a model, and the work may be published at length (public domain or a recorded licence)."""
    p = []
    try:
        e, b = book(obj["work"]["book_id"])
    except Exception as x:
        return [f"book {obj['work'].get('book_id')} not available here: {type(x).__name__}: {x}"]
    if e.get("file_sha256") != obj["work"].get("file_sha256"):
        p.append("the library's book file is not the edition this excerpt was taken from")
    if e.get("register") == "classical":
        p.append("this edition was read and confirmed classical / semi-classical (editor-in-chief 2026-11-08): not a 原文精选 body")
    if e.get("private") or obj.get("private"):
        p.append("private reading piece from the owner's own books (2026-11-10): kept on this Pi, never admitted to the column")
    cjk = e.get("language", "zh") == "zh"
    cache = data_dir() / "source_cache" / f"{e.get('source_id')}.txt"
    p += checks(obj, b, evidence.normalise(cache.read_text(encoding="utf-8"), cjk) if cache.exists() else None, cjk)
    if obj.get("open_issues"):
        p.append(f"{len(obj['open_issues'])} open review issue(s)")
    if not obj.get("review"):
        p.append("no review record")
    if not obj.get("calls") or any(not c.get("model") for c in obj["calls"]):
        p.append("a model call without a reported model")
    if obj["work"].get("rights") not in ("public_domain", "licensed"):
        p.append(f"rights {obj['work'].get('rights')!r}: long public excerpts need a public-domain or licensed edition")
    if approval is not None and not str(approval).startswith("excerpt-editor:"):
        p.append("approval is not an excerpt-editor approval")
    return p


def admit(db, path: Path) -> dict:
    """Register an episode (passage span + people, for dedupe) and admit the excerpt as `checked` when its record
    verifies; otherwise nothing changes and the problems are returned."""
    path = Path(path).resolve(); obj = json.loads(path.read_text(encoding="utf-8")); render.finalize(obj)
    eid_ = obj["edition_id"]
    if state.get(db, eid_):
        return {"admitted": False, "edition_id": eid_, "reason": f"already known: {state.get(db, eid_)['status']}"}
    probs = record_problems(obj)
    if probs:
        return {"admitted": False, "edition_id": eid_, "problems": probs}
    m = obj.get("episode_meta") or {}
    a, z = obj["passage"][0]["loc"], obj["passage"][-1]["loc"]
    ep = {"title": obj["title"]["zh"], "category": obj["category"], "persons": [n["zh"] for n in obj.get("names") or [] if n.get("zh")][:8] or [obj["work"].get("author_zh") or obj["work"]["author"]],
          "year_from": int(m.get("year_from") or 0), "year_to": int(m.get("year_to") or m.get("year_from") or 0), "place": m.get("place") or "",
          "action": m.get("action") or obj["title"]["zh"], "parent_event": None,
          "spans": [[f"bookfile:{obj['work']['book_id']}", int(a.get("offset", obj["passage"][0]["p"])), int(z.get("offset", obj["passage"][-1]["p"])) + int(z.get("length", 1))]]}
    episode_id, v = registry.reserve(db, ep, status="prepared")
    if not episode_id:
        return {"admitted": False, "edition_id": eid_, "reason": f"episode {v[0]}: {v[1]}"}
    approval = approval_of(obj)
    state.transition(db, eid_, "prepared", note="原文精选: record verified", episode_id=episode_id, category=obj["category"], path=str(path))
    registry.set_status(db, episode_id, "checked")
    state.transition(db, eid_, "checked", note=f"admitted: {approval}", content_sha256=obj["content_sha256"], reason="", approval=approval,
                     origin="excerpt", revision=obj.get("revision") or 1)
    return {"admitted": True, "edition_id": eid_, "approval": approval, "episode_id": episode_id}


# ------------------------------------------------------------------ nightly supply (原文精选 is the default form)

LEDGER = REPO / "config" / "excerpts" / "attempts.jsonl"     # units tried in validation / elsewhere (tracked)


def attempts() -> list[dict]:
    out = []
    for f in (LEDGER, data_dir() / "excerpts" / "attempts.jsonl"):
        if f.exists():
            out += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    return out


def _log(rec: dict) -> None:
    f = data_dir() / "excerpts" / "attempts.jsonl"; f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps(rec, ensure_ascii=False) + "\n")


FOCUS_THEMES = ("经济与金融", "企业与商业", "科学与技术", "政治与治理")   # editor-in-chief 2026-11-09: 读书明事理 needs these too
GENERIC_THEMES = {"人物传记", "历史"}                                  # too broad to tell two issues apart


def recent_mix(db, n: int = 14) -> dict:
    """Themes and authors of the latest n 原文精选 (sent, scheduled or ready; withdrawn ones excluded)."""
    themes, authors = {}, {}
    if db is None:
        return {"themes": themes, "authors": authors}
    lib = {e["book_id"]: e for e in lib_load()["books"]}
    rows = db.execute("SELECT path FROM edition WHERE origin='excerpt' AND status!='rejected' ORDER BY updated_at DESC LIMIT ?", (n,)).fetchall()
    for (path,) in rows:
        try:
            w = json.loads(Path(path).read_text(encoding="utf-8"))["work"]
        except Exception:
            continue
        e = lib.get(w.get("book_id")) or {}
        for t in set(e.get("themes") or []) - GENERIC_THEMES:
            themes[t] = themes.get(t, 0) + 1
        a = w.get("author_zh") or w.get("author")
        if a:
            authors[a] = authors.get(a, 0) + 1
    return {"themes": themes, "authors": authors}


def variety_score(e: dict, mix: dict) -> float:
    """Lower is wanted sooner: the book's least-covered theme lately, a little ahead for the focus themes and for
    Chinese originals, a little behind for an author who appeared lately."""
    ts = [t for t in e.get("themes") or [] if t not in GENERIC_THEMES]
    gap = min((mix["themes"].get(t, 0) for t in ts), default=3)
    return gap - 0.5 * any(t in FOCUS_THEMES for t in ts) - 0.5 * (e.get("language", "zh") == "zh") \
        + 0.5 * mix["authors"].get(e.get("author_zh") or e.get("author"), 0)


def units_open(category: str | None = None, mix: dict | None = None) -> list[dict]:
    """Untried chapter units of books that may be published at length (public domain / licensed). With `mix` (recent
    themes and authors) the order favours missing themes and new authors; without it, Chinese originals first."""
    tried = {(a["book_id"], a["unit"]) for a in attempts()}
    used = {(a["book_id"], a["unit"]) for a in attempts() if a.get("outcome") == "admitted"}
    out = []
    for e in lib_load()["books"]:
        if e.get("level") != "usable" or e.get("exclude") or e.get("excerpt") is False or e.get("register") == "classical" \
                or e.get("private") or e.get("rights") not in ("public_domain", "licensed"):
            continue
        if category and category not in (e.get("categories") or []):
            continue
        up = data_dir() / "books" / "units" / f"{e['book_id']}.json"
        if not up.exists():
            continue
        us = json.loads(up.read_text(encoding="utf-8"))["units"]
        for i, u in enumerate(us):
            if (e["book_id"], u["unit"]) in tried:
                continue
            end = us[i + 1]["first_para"] if i + 1 < len(us) else None
            out.append({"book_id": e["book_id"], "unit": u["unit"], "start": u["first_para"], "end": end, "title": u["title"],
                        "lang": e.get("language", "zh"), "category": (e.get("categories") or ["china_modern"])[0] if not category else category,
                        "n_used": sum(1 for b, _ in used if b == e["book_id"]),
                        "variety": variety_score(e, mix) if mix is not None else 0.0})
    return sorted(out, key=lambda x: (x["variety"], x["lang"] != "zh", x["n_used"], x["book_id"], x["unit"]))


def supply(db, categories: list[str], *, target: int = 6, max_runs: int = 2, call=None, today: str | None = None) -> list[dict]:
    """Keep about `target` admitted, unscheduled 原文精选 ready. One chain run per unit; a clean result (checks pass, no
    open review issue) is written to samples/excerpts/<id>/ and admitted; anything else stays a record. Bounded."""
    ready = db.execute("SELECT COUNT(*) FROM edition WHERE status='checked' AND origin='excerpt'").fetchone()[0]
    out = []
    if ready >= target:
        return [{"outcome": "enough", "ready": ready, "target": target}]
    today = (today or time.strftime("%Y%m%d"))
    rank = {c: i for i, c in enumerate(categories)}
    while len(out) < max_runs:
        # editor-in-chief 2026-11-09: missing themes (economy, business, science, political decisions) and new authors
        # first; the mix gaps (categories, in order) and Chinese originals break ties. Recomputed after each run.
        cand = sorted(units_open(None, recent_mix(db)), key=lambda u: (u["variety"], rank.get(u["category"], len(rank))))
        if not cand:
            break
        u = cand[0]
        if u["end"] is None:
            u["end"] = len(book(u["book_id"])[1]["paragraphs"])
        eid = f"excerpt-{today}-{u['book_id'].lower().removeprefix('bk-')}-u{u['unit']}"
        rec = {"at": time.time(), "book_id": u["book_id"], "unit": u["unit"], "edition_id": eid, "category": u["category"]}
        try:
            o = run(u["book_id"], (u["start"], u["end"]), eid, u["category"], call=call)
        except Exception as x:
            o = {"outcome": "error", "reason": f"{type(x).__name__}: {x}"[:300]}
        if o.get("kind") != "excerpt":
            _log(rec | {"outcome": o.get("outcome"), "reason": o.get("reason")}); out.append(rec | {"outcome": o.get("outcome"), "reason": o.get("reason")})
            if o.get("outcome") == "failed":
                return out                          # the model is unavailable or failing: stop for tonight
            continue
        if o.get("checks") or o.get("open_issues"):
            why = "; ".join(o.get("checks") or [] ) or f"{len(o['open_issues'])} open review issue(s)"
            _log(rec | {"outcome": "held", "reason": why[:300]}); out.append(rec | {"outcome": "held", "reason": why[:300]}); continue
        dest = ADMIT_ROOT / eid / "excerpt.json"; dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
        a = admit(db, dest)
        _log(rec | {"outcome": "admitted" if a.get("admitted") else "refused", "reason": a.get("reason") or "; ".join(a.get("problems") or [])})
        out.append(rec | {"outcome": "admitted" if a.get("admitted") else "refused", "title": o["title"]["zh"], "minutes": o.get("reading_minutes")})
    return out


def readmit(db, path: Path, reason: str) -> dict:
    """An operator's recorded edit to an admitted, not yet scheduled 原文精选 (byline, a label, a note): the record is
    re-verified exactly as at admission and the edition moves checked -> pending_review -> prepared -> checked with the
    new content hash; the episode is kept. Never for a scheduled or sent edition."""
    path = Path(path).resolve(); obj = json.loads(path.read_text(encoding="utf-8")); render.finalize(obj)
    cur = state.get(db, obj["edition_id"])
    if not cur or cur["status"] != "checked":
        return {"admitted": False, "edition_id": obj["edition_id"], "reason": f"status {cur['status'] if cur else 'unknown'}: only a checked, unscheduled edition"}
    probs = record_problems(obj)
    if probs:
        return {"admitted": False, "edition_id": obj["edition_id"], "problems": probs}
    approval = approval_of(obj)
    state.transition(db, obj["edition_id"], "pending_review", note=f"operator edit: {reason}"[:500], reason="re-admission")
    state.transition(db, obj["edition_id"], "prepared", note="原文精选: record re-verified", path=str(path))
    state.transition(db, obj["edition_id"], "checked", note=f"re-admitted: {approval}", content_sha256=obj["content_sha256"], reason="",
                     approval=approval, origin="excerpt", revision=obj.get("revision") or 1)
    return {"admitted": True, "edition_id": obj["edition_id"], "approval": approval}

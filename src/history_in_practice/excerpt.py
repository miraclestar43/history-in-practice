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
from . import books, evidence, editor, render
from .config import data_dir
from .library import get as lib_get, load as lib_load
from .pipeline import load_prompt

GAP = "〔中略〕"
TIMEOUT = {"select": 900, "guide": 900, "translate": 1800, "review": 1200}
MAX_WINDOW_CHARS = {True: 40000, False: 90000}


def book(book_id: str) -> tuple[dict, dict]:
    e = lib_get(lib_load(), book_id)
    f = next(x for x in json.loads((data_dir() / "books" / "manifest.json").read_text())["files"] if x["book_id"] == book_id)
    b = books.parse(data_dir() / "books" / "files" / f["path"])
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


def extract(b: dict, sel: dict) -> list[dict]:
    """The passage, from the saved book: paragraphs start..end, whole-paragraph omissions marked by gap_before."""
    a, z = int(sel["start"]), int(sel["end"])
    omit = {k for x, y in sel.get("omit") or [] for k in range(int(x), int(y) + 1)}
    if not (0 <= a <= z < len(b["paragraphs"])):
        raise ValueError(f"paragraph range {a}-{z} outside the book")
    if any(not (a < k < z) for k in omit):
        raise ValueError("an omission must lie strictly inside the passage")
    out, gap = [], False
    for k in range(a, z + 1):
        if k in omit:
            gap = True; continue
        p = b["paragraphs"][k]
        out.append({"p": k, "orig": p["text"], "loc": p["loc"], "gap_before": gap}); gap = False
    return out


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
        if prev is not None and x["p"] != prev + 1 and not x["gap_before"]:
            p.append(f"P{x['p']}: paragraphs skipped without a 〔中略〕 mark")
        if prev is not None and x["p"] == prev + 1 and x["gap_before"]:
            p.append(f"P{x['p']}: 〔中略〕 where nothing was left out")
        if not (x.get(tr) or "").strip():
            p.append(f"P{x['p']}: translation missing")
        prev = x["p"]
    by = {x["p"]: x for x in obj["passage"]}
    for i, n in enumerate(obj.get("notes") or []):
        if n.get("para") not in by:
            p.append(f"note {i + 1}: paragraph P{n.get('para')} is not in the passage")
        elif n.get("term") and n["term"] not in by[n["para"]][lang]:
            p.append(f"note {i + 1}: term {n['term']!r} not in P{n['para']}")
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
    meta = (f"【书目】{e.get('author')}《{e['title']}》；版本：{e.get('edition') or '见来源'}；原文语言：{'中文' if cjk else '英文'}；"
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
    for rnd in (1, 2):
        rv = caller(f"review_r{rnd}", f"{load_prompt('excerpt_review')}\n\n{meta}\n\n【前文】\n{_context(b, int(sel['start']))}\n\n"
                                      f"【本期】\n{json.dumps(view(obj), ensure_ascii=False, indent=1)}",
                    TIMEOUT["review"], "\n\n[Reply with one valid JSON object only.]", validate=_schema("review"))
        if rv is None:
            obj["review"].append({"round": rnd, "failed": True}); break
        fixes = [i for i in rv["issues"] if i.get("severity") == "fix"]
        applied = [apply_fix(obj, i) for i in fixes] if rnd == 1 else []
        obj["review"].append({"round": rnd, "reading": rv.get("reading"), "issues": rv["issues"], "applied": applied})
        if rnd == 1 and not any(applied):
            break
    obj["open_issues"] = [i for i in (obj["review"][-1].get("issues") or []) if i.get("severity") == "fix" and not i.get("_applied")]
    cache = data_dir() / "source_cache" / f"{e.get('source_id')}.txt"
    obj["checks"] = checks(obj, b, evidence.normalise(cache.read_text(encoding="utf-8"), cjk) if cache.exists() else None, cjk)
    obj["calls"] = [{k: m.get(k) for k in ("step", "attempt", "wall_s", "json_ok", "schema_ok", "prompts")} | {"model": (m.get("meta") or {}).get("model")}
                    for m in caller.metrics]
    render.finalize(obj)
    (out / "excerpt.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return obj


def apply_fix(obj: dict, i: dict) -> bool:
    """A review fix may replace the editor's text (intro / notes / after / dek) or one translation paragraph; never the
    original. Selection-level problems are reported, not applied."""
    w, new = str(i.get("where") or ""), i.get("proposed")
    if not isinstance(new, str) or not new.strip():
        return False
    lang = obj["work"]["original_language"]; tr = "en" if lang == "zh" else "zh"
    m = re.fullmatch(r"(intro|after|dek)\.(zh|en)", w)
    if m and (obj.get(m.group(1)) or {}).get(m.group(2)) is not None:
        obj[m.group(1)][m.group(2)] = new; i["_applied"] = True; return True
    m = re.fullmatch(r"tr\.P(\d+)", w)
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
    if not m:
        return head, head
    n = _roman(m.group(1)); t = (m.group(2) or "").title().replace(" With ", " with ").replace(" To ", " to ").replace(" Of ", " of ").replace(" The ", " the ")
    return (f"第{_cn(n)}章" if n else head), f"Chapter {m.group(1)}" + (f", “{t}”" if t else "")


def assemble(e: dict, b: dict, sel: dict, guide: dict, passage: list[dict], edition_id: str, category: str) -> dict:
    lang = "zh" if e.get("language", "zh") == "zh" else "en"
    first, last = passage[0]["p"], passage[-1]["p"]
    head = chapter_heading(b, first); ch_zh, ch_en = chapter_labels(head)
    return {"kind": "excerpt", "schema_version": "excerpt/1", "edition_id": edition_id, "revision": 1, "category": category,
            "title": sel["title"], "title_note": {"zh": "编辑拟题", "en": "Title by the editor"},
            "dek": guide["dek"], "intro": guide["intro"], "preheader": guide["dek"],
            "work": {"book_id": e["book_id"], "author": e.get("author_en") or e.get("author"), "author_zh": e.get("author_zh") or e.get("author"),
                     "title": e["title"], "title_zh_note": e.get("title_zh_note"), "chapter_zh": ch_zh, "chapter_en": ch_en,
                     "rights_label": e.get("rights_label"), "edition": e.get("edition"),
                     "original_language": lang, "chapter": head, "paragraphs": [first, last],
                     "location": f"{head}; paragraphs {first}–{last} of the edition's text" + (" (with omissions marked 〔中略〕)" if any(x["gap_before"] for x in passage) else ""),
                     "file_sha256": e.get("file_sha256"), "rights": e.get("rights"), "rights_note": e.get("rights_note"),
                     "reading_url": e.get("reading_url")},
            "translation": {"lang": "en" if lang == "zh" else "zh", "label": {"zh": "AI 译文", "en": "AI translation"},
                            "by": "Claude Opus (claude-opus-5-5) via Claude Code CLI"},
            "passage": passage, "names": guide.get("names") or [], "notes": guide.get("notes") or [],
            "after": guide.get("after"), "continue": guide.get("continue"),
            "selection": {k: sel.get(k) for k in ("start", "end", "omit", "why", "standalone", "context_needed", "omit_check")}}

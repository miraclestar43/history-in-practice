"""Book library for continuous supply (2026-11-01): which books exist, which can actually be read, and which feed the
nightly candidate pool -- by chapter, with stable locations back into the book.

Levels (a catalogue count is never a count of usable books):
  catalogued  listed in a repository tree or a catalogue only (data/books/remote, forks, discovery DB)
  acquired    the file is on the Pi: pinned repo commit + path, git blob verified, sha256 (data/books/manifest.json)
  readable    parsed: TXT/EPUB text, or a PDF with a real text layer (scans are refused), enough paragraphs
  usable      ingested as a book_file source (source cache + location map) with chapter units: in the supply pool
  unsuitable  readable or not, but not for this column (reason recorded): scanned, novelised, theory only, ...

Public Git keeps only config/books/library.json (metadata, levels, reasons, hashes, unit titles). Book files, parsed
text and caches stay under data/books and data/source_cache.

Evidence roles: `genre` says what kind of book it is. Candidates label every excerpt with whose voice it is
(当事人 / 作者 / 译注 / 后世评论 / 文学化); 文学化 passages are never evidence (supply.validate drops them), and a
book whose genre is `novelised` is never in the pool.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from . import books, evidence
from .config import REPO, data_dir

LIB = REPO / "config/books/library.json"
LEVELS = ("catalogued", "acquired", "readable", "usable", "unsuitable")
GENRES = ("memoir", "biography", "scholarly_history", "popular_history", "essay", "letters", "novelised")
UNIT_MAX = {True: 14000, False: 40000}          # normalised characters per unit (below supply.MAX_WINDOW)
UNIT_MIN = {True: 2500, False: 6000}
FRONT = re.compile(r"目录|目錄|序言|自序|序例|前言|后记|後記|出版说明|版权|致谢|致謝|索引|参考文献|參考文獻|附录|附錄|Contents|Preface|Acknowledg|Index|Copyright|Bibliography", re.I)
MIN_PARAS, MIN_CJK_SHARE = 40, 0.6
# owner 2026-11-01: no further stories about these people for now (the first two issues); their chapters stay out of the pool
PAUSED_PEOPLE = re.compile(r"胡適|胡适|吳起|吴起")


def load() -> dict:
    return json.loads(LIB.read_text(encoding="utf-8")) if LIB.exists() else {"schema": "library/1", "books": []}


def save(lib: dict):
    LIB.parent.mkdir(parents=True, exist_ok=True)
    lib["books"].sort(key=lambda b: (LEVELS.index(b.get("level", "catalogued")), b["book_id"]))
    LIB.write_text(json.dumps(lib, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def get(lib: dict, book_id: str) -> dict:
    return next(b for b in lib["books"] if b["book_id"] == book_id)


def manifest() -> list[dict]:
    p = data_dir() / "books" / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8"))["files"] if p.exists() else []


def readability(b: dict, lang: str) -> list[str]:
    """Reasons a parsed book cannot be read reliably (empty = readable)."""
    why = []
    if b.get("format") == "pdf" and b.get("pdf_text_status") != "text":
        why.append(f"PDF without a usable text layer ({b.get('pdf_text_status')}); OCR is out of scope")
    if len(b["paragraphs"]) < MIN_PARAS and sum(len(p["text"]) for p in b["paragraphs"]) < 50000:
        why.append(f"only {len(b['paragraphs'])} paragraphs")
    q = b.get("quality") or {}
    if lang == "zh" and q.get("cjk_share") is not None and q["cjk_share"] < MIN_CJK_SHARE:
        why.append(f"CJK share {q['cjk_share']} (garbled or mostly non-Chinese text layer)")
    if q.get("junk_share", 0) > 0.05:
        why.append(f"junk share {q['junk_share']}")
    return why


def _chapter_starts(b: dict) -> list[tuple[int, str]]:
    """(first paragraph index, title) per detected chapter, in reading order."""
    out = []
    for c in b.get("chapters") or []:
        if "first_para" in c:
            k = c["first_para"]
        elif "spine" in c:
            k = next((i for i, p in enumerate(b["paragraphs"]) if p["loc"].get("spine", -1) >= c["spine"]), None)
        elif "offset" in c:
            k = next((i for i, p in enumerate(b["paragraphs"]) if p["loc"].get("offset", -1) >= c["offset"]), None)
        else:
            k = None
        if k is not None and (not out or k > out[-1][0]):
            out.append((k, c.get("title", "")))
    return out


def units(b: dict, lmap: list[dict], cjk: bool) -> list[dict]:
    """Chapter-sized windows over the normalised source text. Walks the paragraphs in order: a new unit starts at a
    chapter boundary once the current one has UNIT_MIN characters (small sections are merged, e.g. lecture 节), and
    at UNIT_MAX regardless; front-matter chapters (目录, 序, 索引 ...) are left out; no detected chapters -> fixed chunks."""
    starts = dict(_chapter_starts(b))
    skip, cur_title = set(), ""
    for k in range(len(lmap)):
        if k in starts:
            cur_title = starts[k]
        if cur_title and FRONT.search(cur_title):
            skip.add(k)
    out, a, title = [], None, ""

    def close(z):
        s, e = lmap[a]["start"], lmap[z - 1]["end"]
        if e - s >= UNIT_MIN[cjk]:
            covered = [title] * bool(title) + [starts[k] for k in range(a + 1, z) if k in starts]
            out.append({"title": " / ".join(dict.fromkeys(x[:30] for x in covered if x))[:90], "a": s, "b": e, "first_para": a, "location": books.locator(b, b["paragraphs"][a]["loc"])})
    chapter = ""                                          # the chapter paragraph k belongs to
    for k in range(len(lmap)):
        chapter = starts.get(k, chapter)
        if k in skip:
            if a is not None:
                close(k); a = None
            continue
        if a is None:
            a, title = k, chapter
            continue
        size = lmap[k]["end"] - lmap[a]["start"]
        if (k in starts and lmap[k - 1]["end"] - lmap[a]["start"] >= UNIT_MIN[cjk]) or size > UNIT_MAX[cjk]:
            close(k); a, title = k, chapter
    if a is not None:
        close(len(lmap))
    for k, u in enumerate(out):
        u["unit"] = k
    return out


def ingest(book_id: str, *, verified: str) -> dict:
    """acquired -> readable -> usable (or unsuitable with reasons). Writes the source cache, its location map and the unit list."""
    lib = load(); e = get(lib, book_id); f = next(x for x in manifest() if x["book_id"] == book_id)
    path = data_dir() / "books" / "files" / f["path"]
    b = books.parse(path)
    if b["file_sha256"] != f["file_sha256"]:
        raise books.BookError(f"{book_id}: file changed since acquisition")
    cjk = e.get("language", "zh") == "zh"
    e.update(file_sha256=b["file_sha256"], bytes=b["bytes"], format=b["format"], paragraphs=len(b["paragraphs"]),
             chapters_detected=len(b.get("chapters") or []))
    why = readability(b, e.get("language", "zh"))
    if why:
        e.update(level="unsuitable", reason="; ".join(why)); save(lib); return e
    if e.get("genre") == "novelised":
        e.update(level="unsuitable", reason="novelised/popular narrative: discovery only, never evidence"); save(lib); return e
    sid = e.get("source_id") or f"S-{book_id}"
    meta = {k: e.get(k) for k in ("title", "author", "translator", "edition", "year", "language", "genre")} | {
        "must_contain": [], "verified": True, "verified_note": verified, "repo": e.get("repo"), "ref": e.get("ref"), "repo_path": e.get("repo_path")}
    cache = data_dir() / "source_cache"
    m = books.to_source(b, sid, cache, meta, cjk=cjk)
    lmap = json.loads((cache / f"{sid}.locmap.json").read_text(encoding="utf-8"))["map"]
    us = units(b, lmap, cjk)
    (data_dir() / "books" / "units").mkdir(parents=True, exist_ok=True)
    (data_dir() / "books" / "units" / f"{book_id}.json").write_text(json.dumps({"text_sha256": m["text_sha256"], "units": us},
                                                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    if m["status"] != "evidence_usable" or not us:
        e.update(level="readable", reason=f"source status {m['status']}; units {len(us)}"); save(lib); return e
    e.update(level="usable", source_id=sid, text_sha256=m["text_sha256"], units=len(us), reason=None,
             unit_titles=[u["title"] for u in us][:60])
    save(lib); return e


def sync(*, opener=None, tree_of=None) -> list[dict]:
    """Make this data directory match config/books/library.json: every book recorded as usable is acquired (one file
    from its pinned repository commit, git blob verified) if missing, then ingested. Used to deploy the library."""
    import urllib.request
    out, have = [], {f["book_id"] for f in manifest()}
    for e in [x for x in load()["books"] if x.get("level") == "usable"]:
        r = {"book_id": e["book_id"]}
        if e["book_id"] not in have:
            if not (e.get("repo") and e.get("ref") and e.get("repo_path")):
                out.append(dict(r, outcome="missing", reason="file not on this Pi and no pinned repository path")); continue
            tree = (tree_of or (lambda repo, ref: json.loads(urllib.request.urlopen(urllib.request.Request(
                f"https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1", headers={"User-Agent": books.UA,
                "Accept": "application/vnd.github+json"}), timeout=60).read())["tree"]))(e["repo"], e["ref"])
            loc = books.fork_file(e["repo"], e["ref"], tree, e["repo_path"])
            books.acquire(loc["url"], data_dir() / "books" / "files", data_dir() / "books" / "manifest.json",
                          {k: e.get(k) for k in ("title", "author", "translator", "year", "language", "genre")} | {
                              "book_id": e["book_id"], "format": Path(e["repo_path"]).suffix.lstrip(".").lower(), "git_blob": loc["git_blob"],
                              "repo": e["repo"], "ref": e["ref"], "repo_path": e["repo_path"], "upstream": e["repo"],
                              "provenance": f"{e['repo']} at {e['ref']}; path {e['repo_path']}"}, opener=opener)
            r["acquired"] = True
        got = ingest(e["book_id"], verified="file blob-verified against the pinned repository commit; edition = that file")
        out.append(dict(r, outcome=got.get("level"), units=got.get("units"), reason=got.get("reason")))
    return out


def entries(category: str | None = None) -> list[dict]:
    """Supply entries for every unit of every usable book (optionally for one rotation category)."""
    out = []
    for e in load()["books"]:
        if e.get("level") != "usable" or e.get("exclude") or (category and category not in e.get("categories", [])):
            continue
        p = data_dir() / "books" / "units" / f"{e['book_id']}.json"
        if not p.exists():
            continue
        cjk = e.get("language", "zh") == "zh"
        for u in json.loads(p.read_text(encoding="utf-8"))["units"]:
            if PAUSED_PEOPLE.search(u["title"]):
                continue
            out.append({"id": f"{e['book_id']}-u{u['unit']}", "kind": "book", "book_id": e["book_id"], "unit": u["unit"],
                        "category": category or e["categories"][0], "adapter": "book_file", "ref": f"book:{e['book_id']}",
                        "cache_id": e["source_id"], "cjk": cjk, "basis": e["book_id"].lower(), "must_contain": [],
                        "title": f"{e.get('author')}《{e['title']}》" + (f"（{e['translator']} 译）" if e.get("translator") else "")
                                 + (f"，{e['edition']}" if e.get("edition") else "") + (f"；{u['title']}" if u["title"] else ""),
                        "offsets": [u["a"], u["b"]], "unit_title": u["title"], "unit_location": u["location"],
                        "book": {k: e.get(k) for k in ("book_id", "title", "author", "translator", "edition", "year", "genre", "repo",
                                                       "ref", "repo_path", "git_blob", "file_sha256", "source_id")}})
    return out


def inventory() -> dict:
    """Counts by level, plus the catalogue-only file count from saved repository trees (leads, not books)."""
    lib = load(); by = {lv: [b["book_id"] for b in lib["books"] if b.get("level") == lv] for lv in LEVELS}
    leads = 0
    for t in (data_dir() / "books" / "remote").glob("*.tree.json"):
        tree = json.loads(t.read_text(encoding="utf-8")); tree = tree.get("tree", tree) if isinstance(tree, dict) else tree
        leads += sum(1 for x in tree if x.get("type") == "blob" and x["path"].lower().endswith((".epub", ".txt", ".pdf", ".mobi", ".md")))
    return {"catalogued_files_in_saved_trees": leads, "by_level": {k: len(v) for k, v in by.items()}, "books": by,
            "units_in_pool": len(entries())}

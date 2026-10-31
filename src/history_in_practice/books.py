"""Book intake pilot: discovery catalogue (leads only) and bounded TXT/EPUB ingestion.

Discovery: catalogue metadata (e.g. jbiaojerry/ebook-treasure-chest docs/books.json) goes into a separate
SQLite file (data/books/discovery.sqlite). Entries are deduplicated by normalised title/author, keep every
provenance row (catalogue, category, link host) and merged tags, and stay `lead`: a catalogue entry is never
evidence and its download links are not followed (third-party hosts, permission unverified).

Ingestion: owner-provided, public-domain or openly licensed files only, acquired with hard caps
(LIMITS). Book content is untrusted data:
* EPUB: ZIP bounds (member count, per-member and total uncompressed size, compression ratio, no absolute or
  `..` names), DRM/encryption refused, XML with DOCTYPE/ENTITY declarations refused (no entity expansion,
  no external retrieval), XHTML read with html.parser (character references only), nothing executed.
* TXT: BOM / UTF-8 / GB18030 / Big5 detection, newline and Unicode normalisation, Project Gutenberg
  header/licence removed, hard-wrapped lines joined into paragraphs.
Locations are stable and never print pages: EPUB {spine, href, para}; TXT {offset, length} into the
normalised text plus its SHA-256. to_source() writes the text into the source cache with a location map so
the existing evidence-pack builder (evidence.build) cuts verbatim excerpts that map back to a book location.
"""
from __future__ import annotations
import hashlib, html, html.parser, json, posixpath, re, sqlite3, time, unicodedata, urllib.request, zipfile, io
from pathlib import Path
from xml.etree import ElementTree as ET
from . import evidence
from .textnorm import t2s

LIMITS = {"max_files": 3, "max_file_bytes": 50 * 2**20, "max_total_bytes": 200 * 2**20,
          "zip_members": 3000, "zip_member_bytes": 30 * 2**20, "zip_total_bytes": 300 * 2**20, "zip_ratio": 200}
UA = "history-in-practice-books/0.1 (+https://github.com/miraclestar43/history-in-practice)"
BLOCK = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "dd", "dt", "pre", "td", "th", "div", "section", "tr", "table", "ul", "ol"}
HEAD = {"h1", "h2", "h3", "h4"}


class BookError(ValueError):
    pass


# ------------------------------------------------------------------ discovery catalogue (leads)

def _norm_title(t: str) -> tuple[str, list[str]]:
    t = unicodedata.normalize("NFKC", t2s(t or ""))
    notes = re.findall(r"[（(【\[]([^）)】\]]*)[）)】\]]", t)
    key = re.sub(r"[（(【\[][^）)】\]]*[）)】\]]", "", t)
    key = re.sub(r"[\s《》〈〉「」『』“”\"'·・:：,，.。!！?？\-—_]+", "", key).lower()
    return key, [n.strip() for n in notes if n.strip()]


def _norm_author(a: str) -> str:
    a = unicodedata.normalize("NFKC", t2s(a or ""))
    return "/".join(sorted(re.sub(r"[\s·・.]+", "", x).lower() for x in re.split(r"[/、,，;；&]| 等$|等$", a) if x.strip()))


def catalogue_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), isolation_level=None)
    db.executescript("""CREATE TABLE IF NOT EXISTS lead(
        key TEXT PRIMARY KEY, title TEXT, author TEXT, edition_notes TEXT, tags TEXT, languages TEXT, formats TEXT,
        provenance TEXT, status TEXT NOT NULL DEFAULT 'lead', note TEXT);""")
    return db


def import_catalogue(db, items: list[dict], source: str) -> dict:
    """Merge catalogue rows into leads. Returns counts. Never marks anything usable as evidence."""
    n_in, new, merged = 0, 0, 0
    db.execute("BEGIN")                                     # one transaction: ~24k rows on an SD card
    for it in items:
        if not isinstance(it, dict) or not it.get("title"):
            continue
        n_in += 1
        tkey, notes = _norm_title(it["title"]); key = f"{tkey}|{_norm_author(it.get('author', ''))}"
        link = str(it.get("link") or "")
        host = re.sub(r"^https?://([^/]+).*$", r"\1", link) if link.startswith("http") else (link[:40] or "none")
        prov = {"catalogue": source, "category": it.get("category"), "title_as_listed": it["title"], "link_host": host,
                "link_status": "not followed: third-party file host, permission unverified" if link.startswith("http") else "no link"}
        row = db.execute("SELECT tags, languages, formats, provenance, edition_notes FROM lead WHERE key=?", (key,)).fetchone()
        if row:
            tags = sorted(set(json.loads(row[0])) | {it.get("category")} - {None})
            langs = sorted(set(json.loads(row[1])) | {it.get("language")} - {None})
            fmts = sorted(set(json.loads(row[2])) | set(it.get("formats") or []))
            provs = json.loads(row[3]) + [prov]; ed = sorted(set(json.loads(row[4])) | set(notes))
            db.execute("UPDATE lead SET tags=?, languages=?, formats=?, provenance=?, edition_notes=? WHERE key=?",
                       (json.dumps(tags, ensure_ascii=False), json.dumps(langs), json.dumps(fmts), json.dumps(provs, ensure_ascii=False),
                        json.dumps(ed, ensure_ascii=False), key)); merged += 1
        else:
            db.execute("INSERT INTO lead VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (key, it["title"], it.get("author", ""), json.dumps(notes, ensure_ascii=False),
                        json.dumps([it.get("category")] if it.get("category") else [], ensure_ascii=False),
                        json.dumps([it.get("language")] if it.get("language") else []), json.dumps(sorted(it.get("formats") or [])),
                        json.dumps([prov], ensure_ascii=False), "lead", None)); new += 1
    db.execute("COMMIT")
    return {"rows": n_in, "new_leads": new, "merged_duplicates": merged, "leads_total": db.execute("SELECT count(*) FROM lead").fetchone()[0]}


# ------------------------------------------------------------------ bounded acquisition

def acquire(url: str, dest_dir: Path, manifest_path: Path, meta: dict, *, opener=None) -> dict:
    """Download one file with the pilot caps; records size, SHA-256 and provenance in a local manifest."""
    man = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": []}
    if len(man["files"]) >= LIMITS["max_files"]:
        raise BookError(f"pilot limit: {LIMITS['max_files']} files already acquired")
    used = sum(f["bytes"] for f in man["files"]); cap = min(LIMITS["max_file_bytes"], LIMITS["max_total_bytes"] - used)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with (opener or urllib.request.urlopen)(req, timeout=60) as r:
        ctype = r.headers.get("Content-Type", ""); body = r.read(cap + 1)
    if len(body) > cap:
        raise BookError(f"file exceeds the pilot cap ({cap} bytes)")
    if "html" in ctype.lower() and not meta["format"] == "html":
        raise BookError(f"got {ctype!r} instead of a {meta['format']} file (login, challenge or error page)")
    sha = hashlib.sha256(body).hexdigest(); dest_dir.mkdir(parents=True, exist_ok=True)
    p = dest_dir / f"{meta['book_id']}.{meta['format']}"; p.write_bytes(body)
    rec = dict(meta, url=url, bytes=len(body), file_sha256=sha, content_type=ctype, acquired_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"), path=p.name)
    man["files"] = [f for f in man["files"] if f["book_id"] != meta["book_id"]] + [rec]
    manifest_path.write_text(json.dumps(man, ensure_ascii=False, indent=1)); return rec


# ------------------------------------------------------------------ TXT

def decode(data: bytes) -> tuple[str, str]:
    for bom, enc in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
        if data.startswith(bom):
            return data.decode(enc), enc
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    ok = {}
    for enc in ("gb18030", "big5"):                      # Big5 bytes often also "decode" as GB18030 (to nonsense)
        try:
            ok[enc] = data.decode(enc)
        except UnicodeDecodeError:
            continue
    if not ok:
        raise BookError("unknown text encoding (not UTF-8/16, GB18030 or Big5)")
    punct = lambda t: sum(t.count(c) for c in "，。、：；！？「」『』（）《》")   # a correct decode has real CJK punctuation
    enc = max(ok, key=lambda k: (punct(ok[k]), k == "gb18030"))
    return ok[enc], enc


def _strip_gutenberg(lines: list[str]) -> tuple[list[str], bool]:
    s = next((i for i, l in enumerate(lines) if re.match(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG", l, re.I)), None)
    e = next((i for i, l in enumerate(lines) if re.match(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG", l, re.I)), None)
    if s is None and e is None:
        return lines, False
    return lines[(s + 1 if s is not None else 0):(e if e is not None else len(lines))], True


CHAPTER_RE = re.compile(r"^(CHAPTER|Chapter|BOOK|PART)\b.{0,60}$|^第[一二三四五六七八九十百零〇\d]+[章回节節篇卷].{0,30}$")


def parse_txt(data: bytes) -> dict:
    text, enc = decode(data)
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    lines, stripped = _strip_gutenberg(text.split("\n"))
    norm = "\n".join(l.rstrip() for l in lines).strip("\n") + "\n"
    paras, chapters, off = [], [], 0
    for block in re.split(r"\n\s*\n", norm):
        start = norm.find(block, off); off = start + len(block)
        body = block.strip()
        if not body:
            continue
        joined = re.sub(r"\s*\n\s*", "" if re.search(r"[一-鿿]", body) else " ", body)
        if CHAPTER_RE.match(joined) and len(joined) < 80:
            chapters.append({"title": joined, "first_para": len(paras)})
        paras.append({"loc": {"offset": start, "length": len(block)}, "chapter": max(0, len(chapters) - 1), "text": joined})
    return {"format": "txt", "encoding": enc, "gutenberg_boilerplate_removed": stripped,
            "norm_sha256": hashlib.sha256(norm.encode()).hexdigest(), "norm_text": norm, "chapters": chapters, "paragraphs": paras}


# ------------------------------------------------------------------ EPUB

class _Blocks(html.parser.HTMLParser):
    """Paragraph-level text from XHTML. Character references only; no scripts, no external anything."""
    def __init__(self):
        super().__init__(convert_charrefs=True); self.out, self.buf, self.skip, self.tag = [], [], 0, None

    def _flush(self):
        t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if t:
            self.out.append((self.tag or "p", t))
        self.buf, self.tag = [], None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head", "title"):
            self.skip += 1
        elif tag in BLOCK:
            self._flush(); self.tag = tag
        elif tag == "br":
            self.buf.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head", "title"):
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK:
            self._flush()

    def handle_data(self, d):
        if not self.skip:
            self.buf.append(d)


def _xml(raw: bytes):
    head = raw[:4096].decode("utf-8", errors="ignore")
    if "<!ENTITY" in head or "<!DOCTYPE" in head and "[" in head.split("<!DOCTYPE", 1)[1].split(">", 1)[0]:
        raise BookError("XML with an internal DTD/entity declarations refused")
    return ET.fromstring(raw)


def _zip_guard(zf: zipfile.ZipFile):
    infos = zf.infolist()
    if len(infos) > LIMITS["zip_members"]:
        raise BookError("too many ZIP members")
    total = 0
    for i in infos:
        n = i.filename
        if n.startswith("/") or ".." in n.split("/") or "\\" in n or ":" in n.split("/")[0]:
            raise BookError(f"unsafe ZIP member name: {n[:60]}")
        if i.flag_bits & 0x1:
            raise BookError("encrypted ZIP member (DRM) refused")
        if i.file_size > LIMITS["zip_member_bytes"]:
            raise BookError(f"ZIP member too large: {n[:60]}")
        if i.compress_size and i.file_size / i.compress_size > LIMITS["zip_ratio"]:
            raise BookError(f"suspicious compression ratio: {n[:60]}")
        total += i.file_size
    if total > LIMITS["zip_total_bytes"]:
        raise BookError("uncompressed EPUB too large")
    names = {i.filename for i in infos}
    if "META-INF/encryption.xml" in names or "META-INF/rights.xml" in names:
        raise BookError("EPUB declares encryption/rights management (DRM) — refused")


def _read(zf, name) -> bytes:
    with zf.open(name) as f:
        b = f.read(LIMITS["zip_member_bytes"] + 1)          # do not trust the header's size
    if len(b) > LIMITS["zip_member_bytes"]:
        raise BookError(f"ZIP member expands beyond the cap: {name[:60]}")
    return b


BOILERPLATE = re.compile(r"PROJECT GUTENBERG|gutenberg\.org/license|Wikisource|维基文库|維基文庫|ws-export|Creative Commons|CC BY-SA|GNU Free Documentation", re.I)


NAV = re.compile(r"^[\s◄►←→«»<>|]*$|^[◄►←→«»]|[◄►←→«»]$|^第[一二三四五六七八九十百零〇\d]+[章回节節篇卷]$|^序例$|^(上一|下一)")
WIKI_LINKS = re.compile(r"^(姊妹计划|姊妹計劃|参阅维基百科|參閱維基百科|閲文言維基大典|阅文言维基大典|版本$|Sister projects|See also)")


def _header_zone(blocks):
    """Wiki-export chapter headers: arrows, neighbouring-chapter labels and sister-project links before the first
    body block (a p/li/blockquote, or any block of >= 40 characters). Navigation is dropped; the longest header block becomes the chapter title."""
    head = 0
    while head < len(blocks) and head < 8 and len(blocks[head][1]) < 40 and blocks[head][0] not in ("p", "li", "blockquote"):
        head += 1
    zone = [b for b in blocks[:head] if not NAV.search(b[1].strip()) and not WIKI_LINKS.match(b[1].strip())]
    body = [b for b in blocks[head:] if not WIKI_LINKS.match(b[1].strip())]
    heads = [x for t, x in zone if t in HEAD] or [x for _, x in zone]
    title = max(heads, key=len) if heads else (body[0][1][:60] if body else "")
    return zone + body, title


def parse_epub(data: bytes) -> dict:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise BookError(f"not an EPUB/ZIP: {e}")
    _zip_guard(zf)
    if "mimetype" not in zf.namelist() or _read(zf, "mimetype").strip() != b"application/epub+zip":
        raise BookError("missing or wrong EPUB mimetype")
    cont = _xml(_read(zf, "META-INF/container.xml"))
    rootfile = next((e.get("full-path") for e in cont.iter() if e.tag.endswith("rootfile")), None)
    if not rootfile:
        raise BookError("container.xml has no rootfile")
    opf = _xml(_read(zf, rootfile)); base = posixpath.dirname(rootfile)
    ns = lambda e: e.tag.split("}")[-1]
    meta = {ns(e): (e.text or "").strip() for e in opf.iter() if ns(e) in ("title", "creator", "language", "identifier", "date", "publisher", "rights")}
    items = {e.get("id"): e for e in opf.iter() if ns(e) == "item"}
    spine = [e.get("idref") for e in opf.iter() if ns(e) == "itemref"]
    paras, chapters, skipped = [], [], []
    for si, idref in enumerate(spine):
        it = items.get(idref)
        if it is None or "html" not in (it.get("media-type") or ""):
            continue
        href = posixpath.normpath(posixpath.join(base, it.get("href")))
        if href.startswith("..") or href not in zf.namelist():
            raise BookError(f"spine item outside the package or missing: {href[:60]}")
        raw = _read(zf, href)
        if b"<!ENTITY" in raw[:4096]:
            raise BookError(f"entity declarations in {href[:60]} refused")
        p = _Blocks(); p.feed(raw.decode("utf-8", errors="replace")); p.close(); p._flush()
        blocks = [(t, x) for t, x in p.out]
        text = " ".join(x for _, x in blocks)
        edge = si < 2 or si >= len(spine) - 3                # licence/credits/about pages sit at the ends
        if not blocks or (edge and len(text) < 6000 and BOILERPLATE.search(text)):
            skipped.append({"spine": si, "href": href, "chars": len(text), "why": "empty" if not blocks else "boilerplate (licence/credits/about)"}); continue
        blocks, title = _header_zone(blocks)
        chapters.append({"spine": si, "href": href, "title": title[:120], "first_para": len(paras)})
        for j, (t, x) in enumerate(blocks):
            paras.append({"loc": {"spine": si, "href": href, "para": j}, "chapter": len(chapters) - 1, "text": unicodedata.normalize("NFC", x)})
    st = next((i for i, p in enumerate(paras) if re.search(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG", p["text"], re.I)), None)
    en = next((i for i, p in enumerate(paras) if re.search(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG", p["text"], re.I)), None)
    if st is not None or en is not None:                        # Gutenberg header/licence inside the spine
        paras = paras[(st + 1 if st is not None else 0):(en if en is not None else len(paras))]
        chapters = [c for c in chapters if any(p["chapter"] == chapters.index(c) for p in paras)]
    if not paras:
        raise BookError("no readable text in the spine")
    norm = "\n\n".join(p["text"] for p in paras)
    return {"format": "epub", "metadata": meta, "spine_items": len(spine), "skipped": skipped, "chapters": chapters, "paragraphs": paras,
            "norm_sha256": hashlib.sha256(norm.encode()).hexdigest()}


def parse(path: Path) -> dict:
    data = Path(path).read_bytes()
    b = parse_epub(data) if Path(path).suffix.lower() == ".epub" else parse_txt(data)
    b["file_sha256"] = hashlib.sha256(data).hexdigest(); b["bytes"] = len(data)
    return b


# ------------------------------------------------------------------ book -> evidence source

def locator(book: dict, loc: dict) -> str:
    if "spine" in loc:
        ch = next((c for c in reversed(book["chapters"]) if c["spine"] <= loc["spine"]), None)
        return f"EPUB spine {loc['spine']} ({loc['href']}{', ' + ch['title'][:40] if ch else ''}), paragraph {loc['para']}"
    return f"TXT offset {loc['offset']}+{loc['length']} (normalised text sha256 {book['norm_sha256'][:12]})"


def to_source(book: dict, sid: str, cache: Path, src_meta: dict, *, cjk: bool) -> dict:
    """Write the book text as a cache source + a location map. Status becomes evidence_usable only when the caller
    has verified the edition (src_meta['verified'] is True) and every must_contain marker is present."""
    paras = [evidence.clean(p["text"]).strip() for p in book["paragraphs"]]
    text = "\n\n".join(paras); sep = 0 if cjk else 1
    lmap, off = [], 0
    for p, t in zip(book["paragraphs"], paras):
        n = len(evidence.normalise(t, cjk))
        lmap.append({"start": off, "end": off + n, "loc": p["loc"]}); off += n + sep
    assert len(evidence.normalise(text, cjk)) == off - sep, "location map out of step with the normalised text"
    missing = [m for m in src_meta.get("must_contain", []) if m not in re.sub(r"\s+", " ", text)]
    status = "evidence_usable" if src_meta.get("verified") and not missing else ("extractable" if missing else "unverified")
    sha = hashlib.sha256(text.encode()).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    (cache / f"{sid}.txt").write_text(text, encoding="utf-8")
    meta = {k: v for k, v in src_meta.items() if k != "verified"} | {
        "source_id": sid, "status": status, "missing_markers": missing, "text_sha256": sha, "cjk": cjk, "adapter": "book_file",
        "file_sha256": book["file_sha256"], "format": book["format"], "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (cache / f"{sid}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (cache / f"{sid}.locmap.json").write_text(json.dumps({"text_sha256": sha, "cjk": cjk, "map": lmap}, ensure_ascii=False), encoding="utf-8")
    return meta


def book_location(cache: Path, sid: str, offset: int) -> dict | None:
    """Map an evidence offset (normalised text) back to the book location."""
    m = json.loads((cache / f"{sid}.locmap.json").read_text(encoding="utf-8"))
    return next((x["loc"] for x in m["map"] if x["start"] <= offset < x["end"]), None)

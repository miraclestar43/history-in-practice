"""Book-intake pilot: a small, varied selection from the discovery leads, each mapped to an openly available
original/translation and checked for actual availability. Writes config/book_candidates/selection.json.
Catalogue leads are discovery only; their download links are never followed. Fiction and novelised biography are
marked as not evidence. Availability = an HTTP fetch of the open copy (status, content type, bytes), not a claim.
usage: .venv/bin/python validation/book_selection.py"""
import json, sqlite3, sys, time, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from history_in_practice import books  # noqa: E402

SEL = [  # (lead title, lead author, theme/category, open copy URL, edition/translator, genre, evidence role, acquired book id)
 ("李鸿章传", "梁启超", "biography · politics · china_modern", "https://zh.wikisource.org/wiki/李鴻章傳", "1901 text, zh.wikisource transcription",
  "contemporary interpretive biography", "interpretation of a contemporary; facts need a second basis", "BK-LHZZ"),
 ("曾国藩家书（全本全注全译）", "曾国藩", "biography · family · governance · china_modern", "https://zh.wikisource.org/wiki/曾國藩家書", "letters (19th c.), zh.wikisource index page",
  "primary: private letters", "primary for his own views and reported events", None),
 ("劝学篇（全本全注全译）", "张之洞", "politics · education reform · china_modern", "https://zh.wikisource.org/wiki/勸學篇", "1898 text, zh.wikisource",
  "primary: political tract", "primary for his argument; not for outcomes", None),
 ("胡适四十自述（作家榜经典文库）", "胡适", "biography · education · china_modern", "https://zh.wikisource.org/wiki/四十自述", "亞東圖書館 1934 first edition (zh.wikisource header)",
  "primary: memoir", "primary for his own account; US copyright status of the 1934 text unverified", None),
 ("幸运儿：晚清留美幼童的故事", "利尔・莱博维茨/马修・米勒", "education · diplomacy · china_modern", "https://www.gutenberg.org/ebooks/54635",
  "lead is a 2011 popular history (copyrighted); open original: Yung Wing, My Life in China and America (1909), PG #54635", "popular history (lead) / memoir (original)",
  "use the 1909 memoir (already a source via en.wikisource); the 2011 book is not acquired", None),
 ("卢作孚套装（全三册）", "鲁/张湛昀", "enterprise · shipping · china_modern", None, "modern compilation; no open copy identified",
  "modern biography/compilation", "lead only; access issue recorded", None),
 ("荣氏百年：中国商业第一家族", "杜博奇", "enterprise · family business · china_modern", None, "2010s popular business history; no open copy",
  "popular history", "lead only; access issue recorded", None),
 ("郁金香热", "迈克・达什", "finance · speculation · world", "https://www.gutenberg.org/ebooks/24518", "open original: Mackay, Extraordinary Popular Delusions (1841/1852), PG #24518",
  "popular history (1841)", "not reliable alone (tulip chapter exaggerated); South Sea/Mississippi chapters need corroboration", "BK-MACKAY"),
 ("国富论（全译本）", "亚当・斯密", "economics · world", "https://www.gutenberg.org/ebooks/3300", "Smith, Wealth of Nations (1776), PG #3300",
  "primary: treatise", "primary for Smith's argument and his reported examples", None),
 ("居里夫人自传（果麦经典）", "玛丽・居里", "science · biography · economics · world", "https://www.gutenberg.org/ebooks/69617",
  "Marie Curie, Pierre Curie (Macmillan 1923), tr. C. and V. Kellogg, PG #69617", "primary: memoir by a participant", "evidence_usable (edition verified from the title page)", "BK-CURIE"),
 ("富兰克林自传", "富兰克林", "biography · enterprise · us", "https://www.gutenberg.org/ebooks/20203", "Franklin, Autobiography, PG #20203",
  "primary: autobiography (self-presentation)", "primary for his own account", None),
 ("论美国的民主（全2册）", "托克维尔", "politics · society · us", "https://www.gutenberg.org/ebooks/815", "Tocqueville, Democracy in America vol. 1, tr. Reeve, PG #815",
  "primary: contemporary observation/analysis", "observer's analysis; not statistics", None),
 ("伯罗奔尼撒战争史（详注修订本）", "修昔底德", "history · politics · war · world", "https://www.gutenberg.org/ebooks/7142", "Thucydides, tr. Crawley, PG #7142",
  "ancient history (speeches reconstructed by the author)", "primary-ish; speeches are Thucydides' reconstructions", None),
 ("胡雪岩（全三册）", "高阳", "finance · biography (fiction)", None, "historical novel (1970s–80s)", "historical fiction / novelised biography",
  "NOT evidence: a novel; at most a pointer to real sources", None),
 ("绝秦书：民国十八年饥馑", "张浩文", "society · famine (fiction)", None, "novel (2013)", "historical fiction", "NOT evidence: a novel", None),
]


def check(url):
    if not url:
        return {"status": "no open copy identified"}
    req = urllib.request.Request(urllib.parse.quote(url, safe=":/?=&+%"), headers={"User-Agent": books.UA})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read(400_000)
            return {"http": r.status, "content_type": r.headers.get("Content-Type", ""), "bytes_read": len(body)}
    except urllib.error.HTTPError as e:
        return {"http": e.code}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"[:120]}


db = sqlite3.connect(str(ROOT / "data/books/discovery.sqlite"))
man = {f["book_id"]: f for f in json.loads((ROOT / "data/books/manifest.json").read_text())["files"]}
out = []
for title, author, theme, url, edition, genre, role, bid in SEL:
    key = f"{books._norm_title(title)[0]}|{books._norm_author(author)}"
    row = db.execute("SELECT tags, provenance FROM lead WHERE key=?", (key,)).fetchone()
    a = check(url); time.sleep(1)
    status = ("acquired + evidence_usable" if bid == "BK-CURIE" else "acquired (parsed; not yet evidence_usable)") if bid else \
             ("not evidence (fiction)" if "NOT evidence" in role else "open copy reachable (not acquired)" if a.get("http") == 200 else
              "access issue: " + (a.get("status") or (f"http {a['http']}" if "http" in a else a.get("error", ""))))
    out.append({"lead": {"title": title, "author": author, "in_discovery_catalogue": bool(row), "catalogue_tags": json.loads(row[0]) if row else None},
                "theme": theme, "open_copy": url, "edition": edition, "genre": genre, "evidence_role": role, "availability_check": a,
                "status": status, "acquired": {k: man[bid][k] for k in ("book_id", "format", "bytes", "file_sha256", "url")} if bid in man else None})
    print(f"{status[:44]:44} | {title} | {a}")
p = ROOT / "config/book_candidates/selection.json"
p.write_text(json.dumps({"checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "catalogue": "jbiaojerry/ebook-treasure-chest docs/books.json (metadata only)",
                         "note": "leads are discovery, not evidence; catalogue download links were not followed", "selection": out}, ensure_ascii=False, indent=1))
print("->", p.relative_to(ROOT))

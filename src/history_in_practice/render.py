"""Render one bilingual content object to email HTML + text/plain, site data
JSON (+ index) and GitHub Markdown (zh/en). Stdlib only; every text field is
HTML-escaped; no model-produced HTML is ever emitted. All channels come from
the same object, so they share edition_id, revision and content_sha256."""
from __future__ import annotations
import hashlib, html, json, re, sys
from pathlib import Path

CAT = {"china_ancient": ("中国古代", "Ancient China"), "world": ("世界史", "World History"),
       "china_modern": ("中国近现代", "Modern China"), "us": ("美国史", "U.S. History")}
BRAND = "没事儿多读书"          # column name (owner decision 2026-10-31, docs/ADDENDUM_READER_FEEDBACK_20261031.md); was 每日一鉴


def dotted(date) -> str:
    """YYYY-MM-DD (edition date in the project timezone, Asia/Shanghai since 2026-11-01) -> YYYY.MM.DD; empty if the object has no real date."""
    return str(date).replace("-", ".") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date or "")) else ""


def headline(obj, lang="zh") -> str:
    """没事儿多读书｜YYYY.MM.DD｜title (the date segment is omitted when the object has no edition date)."""
    return "｜".join(x for x in (BRAND, dotted(obj.get("edition_date")), obj["title"][lang]) if x)


LBL = {"zh": dict(col=BRAND, today="今天可以怎么用", q="想一想", ex="一个参考思路", assume="假设", steps="可以怎么做",
                  alt="另一种合理选择", src="本篇依据", more="想再读一点", unc="出处与不确定性", min="分钟", read_web="在网页阅读",
                  read_en="Read in English", pause="想暂停接收？直接回复这封邮件写“暂停”，维护者会在配置中停发。", feedback="反馈：直接回复本邮件。",
                  edition="期次", stop="先停十秒，想想你会怎么做。"),
       "en": dict(col=BRAND, today="Using it today", q="Think about it", ex="One possible approach", assume="Assumptions",
                  steps="What you could do", alt="Another reasonable choice", src="Sources", more="Read more",
                  unc="Sources and uncertainty", min="min", read_web="Read on the web", read_en="", pause="", feedback="", edition="Edition",
                  stop="Pause for ten seconds and decide what you would do.")}
ACCENT = "#7a5c3e"
TEST_NOTE = {"zh": "测试邮件：用于检查排版与投递，不是正式的一期；每日订阅尚未开始，之后不会自动收到下一期。",
             "en": "TEST: this checks layout and delivery. It is not an official edition; the daily subscription has not started."}
ZH_CPM, EN_WPM = 320, 200   # reading-rate assumptions for the per-language estimate
e = lambda s: html.escape(s or "", quote=True)

BOOK_FILE = re.compile(r"^https?://(raw\.githubusercontent\.com|github\.com)/.+\.(pdf|epub|mobi|azw3|txt|chm|djvu)(\?.*)?$", re.I)


def web_url(u) -> bool:
    """Only a real http(s) URL becomes a link; a missing one (None) is shown as plain text, never as "None"/"null".
    A link straight to a book file in a code repository is never offered to readers (2026-11-01): the book is cited by
    its title and edition instead."""
    return isinstance(u, str) and bool(re.fullmatch(r"https?://\S+", u)) and not BOOK_FILE.match(u)

EXCERPT_KEYS = ("edition_id", "revision", "title", "dek", "intro", "work", "translation", "passage", "notes", "after", "continue")


def canonical(obj) -> str:
    if obj.get("kind") == "excerpt":                 # 原文精选 (2026-11-02): the author's text + the editor's guide + AI translation
        keep = {k: obj.get(k) for k in EXCERPT_KEYS}
        return json.dumps(keep, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    keep = {k: obj[k] for k in ("edition_id","revision","title","dek","sections","reflection","uncertainty_note","sources","further_reading")}
    return json.dumps(keep, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def stats(obj):
    zh = en = 0
    if obj.get("kind") == "excerpt":                 # what each language's reader reads: guide + passage (original or AI translation) + notes
        cnt = lambda s, l: len(re.findall(r"[一-鿿]", s or "")) if l == "zh" else len(re.findall(r"[A-Za-z']+", s or ""))
        for l in ("zh", "en"):
            n = cnt(obj["intro"][l], l) + sum(cnt(x[l], l) for x in obj["passage"]) + sum(cnt(m.get(l), l) for m in obj.get("notes") or [])
            n += cnt((obj.get("after") or {}).get(l), l)
            zh, en = (n, en) if l == "zh" else (zh, n)
        return zh, en
    for s in obj["sections"]:
        for p in s["paras"]:
            zh += len(re.findall(r"[一-鿿]", p["zh"])); en += len(re.findall(r"[A-Za-z']+", p["en"]))
    r = obj["reflection"]
    for k in ("scenario","question"): zh += len(re.findall(r"[一-鿿]", r[k]["zh"])); en += len(re.findall(r"[A-Za-z']+", r[k]["en"]))
    for k in ("assumptions","steps","alternative"):
        zh += len(re.findall(r"[一-鿿]", r["example"][k]["zh"])); en += len(re.findall(r"[A-Za-z']+", r["example"][k]["en"]))
    return zh, en

def finalize(obj):
    zh, en = stats(obj)
    # estimates only; calibrate with real readers (rates are configurable)
    obj["length"] = {"zh_chars": zh, "en_words": en, "basis": "guide + passage + notes" if obj.get("kind") == "excerpt" else "body + question + example; excludes sources and read-more"}
    obj["reading_minutes"] = {"zh": max(1, round(zh / ZH_CPM)), "en": max(1, round(en / EN_WPM)),
                              "basis": f"estimate: {ZH_CPM} zh chars/min, {EN_WPM} en words/min"}
    obj["content_sha256"] = hashlib.sha256(canonical(obj).encode()).hexdigest()
    return obj

def link(obj, lang, base):
    return f"{base}/history/?story={obj['edition_id']}&lang={lang}"

# ---------------- email ----------------
NEWS_SCHEMA = "news3min/v0-prototype"
NEWS_MAX_AGE_H = 26


# What kind of statement the "why" line is (owner feedback 2026-10-31: keep reported fact, a source's judgment and the
# editor's interpretation apart). reported: a stated consequence from the sources; source_judgment: an attributed
# opinion (analyst, publisher, the company itself); interpretation: the editor's own reading.
NEWS_WHY_LABELS = {"reported": "为什么值得知道：", "source_judgment": "来源观点：", "interpretation": "编辑解读："}


def news_why(it: dict) -> str:
    return (NEWS_WHY_LABELS.get(it.get("why_kind"), "为什么值得知道：") + it["why"]) if it.get("why") else ""


def news_problems(snap: dict | None, now_iso: str | None = None) -> list[str]:
    """Consumer-side check of a frozen 3-minute news snapshot (prompts/08 §4). Any problem means the edition goes out
    without news and says so briefly; a stale, degraded or unsourced snapshot is never shown as today's news."""
    from datetime import datetime, timezone
    if not snap:
        return ["no snapshot"]
    p = []
    if snap.get("schema") != NEWS_SCHEMA: p.append(f"schema {snap.get('schema')!r}")
    if snap.get("status") != "ready": p.append(f"status {snap.get('status')!r}")
    items = snap.get("items") or []
    if not 3 <= len(items) <= 5: p.append(f"{len(items)} items (3-5 expected)")
    for i, it in enumerate(items):
        if not (it.get("headline") and it.get("what")): p.append(f"item {i + 1}: headline/what missing")
        if not any(web_url(s.get("url")) for s in it.get("sources") or []): p.append(f"item {i + 1}: no source link")
        if it.get("why") and it.get("why_kind") not in NEWS_WHY_LABELS: p.append(f"item {i + 1}: why_kind must be one of {sorted(NEWS_WHY_LABELS)}")
        if it.get("why") and _restates(it["why"], it.get("headline", "")): p.append(f"item {i + 1}: why restates the headline (omit it instead)")
    try:
        as_of = datetime.fromisoformat(snap["as_of"]); now = datetime.fromisoformat(now_iso) if now_iso else datetime.now(timezone.utc)
        age = (now - as_of).total_seconds() / 3600
        if age > NEWS_MAX_AGE_H or age < -0.1: p.append(f"as_of {snap['as_of']} is {age:.1f} h from now (max {NEWS_MAX_AGE_H} h)")
    except (KeyError, ValueError, TypeError):
        p.append("as_of missing or not ISO")
    return p


def _restates(why: str, headline: str) -> bool:
    """Most of the why line's 2-character runs already occur in the headline: it adds nothing."""
    grams = lambda t: {t[i:i + 2] for i in range(len(t) - 1) if re.match(r"[一-鿿]{2}", t[i:i + 2])}
    w, h = grams(why), grams(headline)
    return len(w) >= 4 and len(w & h) / len(w) >= 0.6


def news_minutes(snap: dict) -> int:
    t = "".join(it.get(k, "") for it in snap.get("items") or [] for k in ("headline", "what", "why", "qualifiers"))
    return max(1, round(len(re.findall(r"[一-鿿]", t)) / ZH_CPM))


def news_html(snap: dict | None, ok: bool) -> str:
    h = f'<h2 id="news" style="font-size:19px;color:#1d1d1f;margin:6px 0 4px;">今日新闻 · 约 {news_minutes(snap) if ok else 1} 分钟</h2>'
    if not ok:
        return h + '<p style="font-size:15px;line-height:1.8;color:#55524d;margin:0 0 24px;">今天的新闻简报暂缺（没有及时、可核对来源的版本），下面直接进入今日故事。</p>'
    out = [h, f'<p style="font-size:13px;color:#8a857d;margin:0 0 14px;">{e(snap["label"]["zh"])}</p>']
    for i, it in enumerate(snap["items"]):
        why = news_why(it)
        srcs = " · ".join(f'<a href="{e(s["url"])}" style="color:{ACCENT};">{e(s["name"])}</a>' if web_url(s.get("url")) else e(s["name"])
                          for s in it.get("sources") or [])
        out.append(f'<p style="font-size:16px;line-height:1.8;margin:0 0 4px;color:#1d1d1f;"><b>{i + 1}. {e(it["headline"])}</b></p>'
                   f'<p style="font-size:15px;line-height:1.85;margin:0 0 4px;color:#24221f;">{e(it["what"])}</p>'
                   + (f'<p style="font-size:15px;line-height:1.85;margin:0 0 4px;color:#3a3732;">{e(why)}</p>' if why else "")
                   + (f'<p style="font-size:13px;line-height:1.7;margin:0 0 4px;color:#8a857d;">{e(it["qualifiers"])}</p>' if it.get("qualifiers") else "")
                   + f'<p style="font-size:13px;line-height:1.7;margin:0 0 16px;color:#8a857d;">来源：{srcs}</p>')
    out.append('<hr style="border:none;border-top:1px solid #d8d2c8;margin:8px 0 22px;">')
    return "\n".join(out)


# Email layout (editor-in-chief 2026-11-01): column · date → title → [在网页阅读] [Read in English] → dek → body; 18px body,
# 20px headings, ~20px total side padding on phones; no internal ids, revisions or review details for readers; notes are
# a short line plus a link (no folding, no script). Both languages stay in full. Takes effect from the next issue.
BODY = "font-size:18px;line-height:1.85;margin:0 0 16px;color:#24221f;"
H2 = f"font-size:20px;line-height:1.45;color:{ACCENT};margin:30px 0 10px;letter-spacing:.02em;"
EMAIL_STYLE = """<style>
@media (min-width:600px){.hip-card{padding:32px 36px 36px !important}}
@media (prefers-color-scheme:dark){.hip-bg{background:#171614 !important}.hip-card{background:#1f1d1a !important;border-color:#34312c !important}
 .hip-card p,.hip-card li,.hip-card h1{color:#e9e5de !important}.hip-card h2{color:#d2a679 !important}.hip-muted{color:#a39d93 !important}
 .hip-card a{color:#d2a679 !important}.hip-btn a{color:#ffffff !important}.hip-btn2{background:#1f1d1a !important}.hip-btn2 a{color:#d2a679 !important}
 .hip-modern{background:#29261f !important}}
</style>"""


def buttons(obj, base, margin="14px 0 18px") -> str:
    """Two tappable links (>= 44px tall) that wrap on narrow screens instead of overflowing; tables for Outlook."""
    def one(href, label, solid):
        td = (f'<td class="{"hip-btn" if solid else "hip-btn2"}" bgcolor="{ACCENT if solid else "#ffffff"}" style="border-radius:6px;'
              + ("" if solid else f"border:1px solid {ACCENT};") + '">')
        return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="display:inline-block;vertical-align:top;margin:0 10px 10px 0;">'
                f'<tr>{td}<a href="{e(href)}" style="display:inline-block;padding:12px 20px;line-height:20px;font-size:16px;font-weight:bold;'
                f'text-decoration:none;color:{"#ffffff" if solid else ACCENT};">{label}</a></td></tr></table>')
    return (f'<div style="margin:{margin};">' + one(link(obj, "zh", base), LBL["zh"]["read_web"], True)
            + one(link(obj, "en", base), LBL["zh"]["read_en"], False) + "</div>")


def notes_line(obj, lang, base) -> str:
    """The end notes in one short paragraph: what the piece rests on, further reading, and where the full notes are."""
    srcs = "；".join(x["citation"] for x in obj["sources"]) if lang == "zh" else "; ".join(x["citation"] for x in obj["sources"])
    more = ("；" if lang == "zh" else "; ").join(m["title"] for m in obj["further_reading"])
    if lang == "zh":
        return f"本篇依据：{srcs}。" + (f"想再读一点：{more}。" if more else "") + "补充说明见网页版。"
    return f"Sources: {srcs}." + (f" Read more: {more}." if more else "") + " Notes on the material are on the web page."


XL = {"zh": dict(intro="导读", text="正文", orig="原文", ai="AI 译文", notes="注释", after="读后", cont="继续阅读", titled="标题为编辑所拟"),
      "en": dict(intro="Introduction", text="The text", orig="Original", ai="AI translation", notes="Notes", after="Afterword", cont="Read on",
                 titled="Title by the editor")}


def byline(obj, lang) -> str:
    W = obj["work"]; src = W["original_language"]
    if lang == "zh":
        return (f"{W.get('author_zh') or W['author']} 著 ·《{W['title']}》" + (f"（{W['title_zh_note']}）" if W.get("title_zh_note") else "")
                + (f" {W['chapter_zh']}" if W.get("chapter_zh") else "") + f" · 原文{'中文' if src == 'zh' else '英文'}"
                + ("" if src == "zh" else " · 下文中文为 AI 译文"))
    return (f"{W['author']}, {W['title']}" + (f", {W['chapter_en']}" if W.get("chapter_en") else "")
            + f" · original in {'Chinese' if src == 'zh' else 'English'}" + ("" if src == "en" else " · the English below is an AI translation"))


def excerpt_block(obj, lang, base, with_buttons=False) -> str:
    """One language of a 原文精选 issue for email: title, byline, (buttons), dek, guide, the text with its label, notes,
    afterword, read-on line. No folding, no script."""
    X = XL[lang]; src = obj["work"]["original_language"]; out = []
    out.append(f'<h1 style="font-family:Georgia,\'Songti SC\',serif;font-size:28px;line-height:1.3;margin:6px 0 4px;color:#1d1d1f;">{e(obj["title"][lang])}</h1>')
    out.append(f'<p class="hip-muted" style="font-size:15px;line-height:1.65;color:#6f6a62;margin:0 0 6px;">{e(byline(obj, lang))}</p>')
    if with_buttons:
        out.append(buttons(obj, base))
    out.append(f'<p class="hip-muted" style="font-size:17px;line-height:1.75;color:#55524d;margin:0 0 18px;">{e(obj["dek"][lang])}</p>')
    out.append(f'<h2 style="{H2}">{X["intro"]}</h2>')
    out += [f'<p style="{BODY}">{e(t)}</p>' for t in obj["intro"][lang].split("\n") if t.strip()]
    label = X["orig"] if lang == src else X["ai"]
    out.append(f'<h2 style="{H2}">{X["text"]} <span style="font-size:13px;border:1px solid {ACCENT};border-radius:10px;padding:1px 8px;vertical-align:2px;">{label}</span></h2>')
    marks = {}
    for i, n in enumerate(obj.get("notes") or []):
        marks.setdefault(n["para"], []).append(i + 1)
    for x in obj["passage"]:
        if x["gap_before"]:
            out.append('<p style="text-align:center;color:#8a857d;letter-spacing:.3em;margin:0 0 16px;">〔中略〕</p>')
        sup = "".join(f'<sup style="font-size:12px;color:{ACCENT};">[{k}]</sup>' for k in marks.get(x["p"], []))
        out.append(f'<p style="{BODY}">{e(x[lang])}{sup}</p>')
    if obj.get("notes"):
        out.append(f'<h2 style="{H2}">{X["notes"]}</h2><ol style="font-size:16px;line-height:1.75;color:#3a3732;padding-left:22px;margin:0 0 10px;">')
        out += [f'<li style="margin-bottom:6px;"><span style="color:#8a857d;">{e(n["term"])}：</span>{e(n[lang])}</li>' for n in obj["notes"]]
        out.append("</ol>")
    if (obj.get("after") or {}).get(lang):
        out.append(f'<h2 style="{H2}">{X["after"]}</h2><p style="{BODY}">{e(obj["after"][lang])}</p>')
    if (obj.get("continue") or {}).get(lang):
        out.append(f'<p class="hip-muted" style="font-size:15px;line-height:1.75;color:#6f6a62;margin:22px 0 0;"><b>{X["cont"]}：</b>{e(obj["continue"][lang])}</p>'
                   .replace("：</b>", ":</b> " if lang == "en" else "：</b>"))
    out.append(f'<p class="hip-muted" style="font-size:14px;line-height:1.75;color:#8a857d;margin:10px 0 0;">{X["titled"]}{"；" if lang == "zh" else "; "}'
               f'{e(obj["work"].get("edition") or "")} '
               f'<a href="{e(link(obj, lang, base))}#notes" style="color:{ACCENT};">{"书目与版本" if lang == "zh" else "Book and edition"}</a></p>')
    return "\n".join(out)


def email_html(obj, base, news: dict | None = None, now_iso: str | None = None):
    cz, ce = CAT[obj["category"]]; date = e(dotted(obj["edition_date"]) or obj["edition_date"])
    def block(lang):
        L = LBL[lang]; out = []
        out.append(f'<h1 style="font-family:Georgia,\'Songti SC\',serif;font-size:28px;line-height:1.3;margin:6px 0 4px;color:#1d1d1f;">{e(obj["title"][lang])}</h1>')
        if lang == "zh":
            out.append(buttons(obj, base))
        out.append(f'<p class="hip-muted" style="font-size:17px;line-height:1.75;color:#55524d;margin:0 0 20px;">{e(obj["dek"][lang])}</p>')
        for s in obj["sections"]:
            if not s["paras"]:
                continue
            out.append(f'<h2 style="{H2}">{e(s["heading"][lang])}</h2>')
            for p in s["paras"]:
                style = BODY + ("background:#f6f2ec;padding:10px 14px;border-radius:4px;" if p["kind"] == "modern" else "")
                cls = ' class="hip-modern"' if p["kind"] == "modern" else ""
                out.append(f'<p{cls} style="{style}">{e(p[lang])}</p>')
        r = obj["reflection"]
        out.append(f'<h2 style="{H2}">{L["q"]}</h2>')
        out.append(f'<p style="{BODY}">{e(r["scenario"][lang])}</p>')
        out.append(f'<p style="font-size:18px;line-height:1.8;margin:0 0 10px;font-weight:bold;color:#1d1d1f;border-left:3px solid {ACCENT};padding-left:12px;">{e(r["question"][lang])}</p>')
        out.append(f'<p class="hip-muted" style="font-size:15px;color:#8a857d;margin:0 0 24px;">{L["stop"]}</p>')
        out.append(f'<p class="hip-muted" style="font-size:16px;font-weight:bold;color:#55524d;margin:26px 0 8px;border-top:1px dashed #d8d2c8;padding-top:14px;">{L["ex"]}</p>')
        sep = "：" if lang == "zh" else ": "
        for k, lab in (("assumptions", L["assume"]), ("steps", L["steps"]), ("alternative", L["alt"])):
            out.append(f'<p style="font-size:16px;line-height:1.8;margin:0 0 10px;color:#3a3732;"><b>{lab}{sep}</b>{e(r["example"][k][lang])}</p>')
        out.append(f'<p class="hip-muted" style="font-size:14px;line-height:1.75;color:#6f6a62;margin:22px 0 0;">{e(notes_line(obj, lang, base))} '
                   f'<a href="{e(link(obj, lang, base))}#notes" style="color:{ACCENT};">{"书目与补充说明" if lang == "zh" else "Sources and notes"}</a></p>')
        return "\n".join(out)
    head = (f'<p class="hip-muted" style="font-size:14px;color:#8a857d;margin:0;letter-spacing:.04em;">{LBL["zh"]["col"]}｜{date} · {cz} · '
            f'中文约 {obj["reading_minutes"]["zh"]} 分钟 · English ~{obj["reading_minutes"]["en"]} min</p>')
    sep_en = (f'<hr style="border:none;border-top:1px solid #d8d2c8;margin:34px 0 26px;">'
              f'<p class="hip-muted" style="font-size:14px;color:#8a857d;margin:0;letter-spacing:.04em;">{LBL["en"]["col"]}｜{date} · {ce} · English</p>')
    foot = (f'<p class="hip-muted" style="font-size:14px;line-height:1.8;color:#8a857d;margin:34px 0 0;border-top:1px solid #e6e1d8;padding-top:14px;">'
            f'{LBL["zh"]["col"]}｜{date}<br><a href="{e(link(obj,"zh",base))}" style="color:{ACCENT};">{LBL["zh"]["read_web"]}</a> · '
            f'<a href="{e(link(obj,"en",base))}" style="color:{ACCENT};">Read in English</a><br>{LBL["zh"]["feedback"]} {LBL["zh"]["pause"]}</p>')
    pre = e(obj["preheader"]["zh"])
    nav = newsblock = ""
    if news is not None:                     # one reading edition, two modules (prompts/08 §1); same text goes to the web copy
        ok = not news_problems(news, now_iso)
        nav = (f'<p style="font-size:15px;margin:10px 0 18px;"><a href="#news" style="color:{ACCENT};">今日新闻 · 约 {news_minutes(news) if ok else 1} 分钟</a>'
               f' · <a href="#story" style="color:{ACCENT};">今日故事 · 约 {obj["reading_minutes"]["zh"]} 分钟</a></p>')
        newsblock = news_html(news, ok)
    if obj.get("status") == "test":
        head = (f'<p style="font-size:14px;line-height:1.7;margin:0 0 16px;padding:10px 14px;border:2px solid #b5542f;color:#7a2e12;border-radius:4px;">'
                f'<b>测试 TEST</b> · {e(TEST_NOTE["zh"])}<br>{e(TEST_NOTE["en"])}</p>') + head
    return f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark"><title>{e(obj["title"]["zh"])}</title>
{EMAIL_STYLE}</head>
<body class="hip-bg" style="margin:0;padding:0;background:#faf8f4;-webkit-text-size-adjust:100%;">
<div style="display:none;max-height:0;overflow:hidden;">{pre}</div>
<table role="presentation" class="hip-bg" width="100%" cellpadding="0" cellspacing="0" style="background:#faf8f4;"><tr><td align="center" style="padding:16px 8px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;"><tr>
<td class="hip-card" style="background:#ffffff;border:1px solid #ece7de;padding:24px 12px 30px;font-family:-apple-system,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',Helvetica,Arial,sans-serif;">
{head}
{nav}{newsblock}<a id="story"></a>
{excerpt_block(obj, "zh", base, True) if obj.get("kind") == "excerpt" else block("zh")}
{sep_en}
{excerpt_block(obj, "en", base) if obj.get("kind") == "excerpt" else block("en")}
{foot}
</td></tr></table></td></tr></table></body></html>'''

def excerpt_text(obj, lang, base, links=False) -> str:
    X = XL[lang]; src = obj["work"]["original_language"]
    out = [obj["title"][lang], byline(obj, lang)] + ([f"在网页阅读：{link(obj,'zh',base)}", f"Read in English：{link(obj,'en',base)}"] if links else [])
    out += ["", obj["dek"][lang], "", f"== {X['intro']} ==", obj["intro"][lang], "", f"== {X['text']}（{X['orig'] if lang == src else X['ai']}）==" if lang == "zh"
            else f"== {X['text']} ({X['orig'] if lang == src else X['ai']}) =="]
    marks = {}
    for i, n in enumerate(obj.get("notes") or []):
        marks.setdefault(n["para"], []).append(i + 1)
    for x in obj["passage"]:
        out += (["〔中略〕", ""] if x["gap_before"] else []) + [x[lang] + "".join(f"[{k}]" for k in marks.get(x["p"], [])), ""]
    if obj.get("notes"):
        out += [f"== {X['notes']} =="] + [f"[{i + 1}] {n['term']}: {n[lang]}" for i, n in enumerate(obj["notes"])] + [""]
    if (obj.get("after") or {}).get(lang):
        out += [f"== {X['after']} ==", obj["after"][lang], ""]
    if (obj.get("continue") or {}).get(lang):
        out += [f"{X['cont']}: {obj['continue'][lang]}"]
    out += [f"{X['titled']}; {obj['work'].get('edition') or ''} {link(obj, lang, base)}#notes"]
    return "\n".join(out)


def email_text(obj, base, news: dict | None = None, now_iso: str | None = None):
    def block(lang, links=False):
        if obj.get("kind") == "excerpt":
            return excerpt_text(obj, lang, base, links)
        L = LBL[lang]; r = obj["reflection"]
        out = [obj["title"][lang]] + ([f"在网页阅读：{link(obj,'zh',base)}", f"Read in English：{link(obj,'en',base)}"] if links else []) + ["", obj["dek"][lang], ""]
        for s in obj["sections"]:
            if s["paras"]:
                out += [f"== {s['heading'][lang]} ==", *[p[lang] + "\n" for p in s["paras"]]]
        out += [f"== {L['q']} ==", r["scenario"][lang], "", r["question"][lang], "", L["stop"], "", "-" * 20, f"{L['ex']}",
                f"{L['assume']}: {r['example']['assumptions'][lang]}", f"{L['steps']}: {r['example']['steps'][lang]}",
                f"{L['alt']}: {r['example']['alternative'][lang]}", "", notes_line(obj, lang, base) + f" {link(obj, lang, base)}#notes"]
        return "\n".join(out)
    test = [f"【测试 TEST】{TEST_NOTE['zh']}", TEST_NOTE["en"], ""] if obj.get("status") == "test" else []
    nw = []
    if news is not None:
        if news_problems(news, now_iso):
            nw = ["== 今日新闻 ==", "今天的新闻简报暂缺（没有及时、可核对来源的版本），下面直接进入今日故事。", ""]
        else:
            nw = [f"== 今日新闻 · 约 {news_minutes(news)} 分钟 ==", news["label"]["zh"], ""]
            for i, it in enumerate(news["items"]):
                nw += [f"{i + 1}. {it['headline']}", it["what"]]
                if it.get("why"): nw.append(news_why(it))
                if it.get("qualifiers"): nw.append(it["qualifiers"])
                nw += ["来源：" + "；".join(s["name"] + (f" {s['url']}" if web_url(s.get("url")) else "") for s in it.get("sources") or []), ""]
            nw += ["=" * 20, "== 今日故事 ==", ""]
    date = dotted(obj['edition_date']) or obj['edition_date']
    return "\n".join(test + nw + [f"{LBL['zh']['col']}｜{date} · {CAT[obj['category']][0]}", "", block("zh", links=True), "",
                      "=" * 40, f"{LBL['en']['col']}｜{date} · {CAT[obj['category']][1]} · English", "", block("en"), "", "=" * 40,
                      f"在网页阅读：{link(obj,'zh',base)}", f"Read in English：{link(obj,'en',base)}", f"{LBL['zh']['feedback']} {LBL['zh']['pause']}"])

def markdown(obj, lang):
    if obj.get("kind") == "excerpt":
        return excerpt_text(obj, lang, "https://starhub.vip") + "\n"
    L = LBL[lang]; r = obj["reflection"]
    out = [f"# {obj['title'][lang]}", "", f"*{obj['dek'][lang]}*", "",
           f"{obj['edition_date']} · {CAT[obj['category']][0 if lang=='zh' else 1]} · {obj['edition_id']} rev {obj['revision']}", ""]
    for s in obj["sections"]:
        out += [f"## {s['heading'][lang]}", ""]
        for p in s["paras"]:
            tag = "" if not p["ev"] else " " + "".join(f"[{x}]" for x in p["ev"])
            out += [(("> " if p["kind"] == "modern" else "") + p[lang] + tag), ""]
    out += [f"## {L['q']}", "", r["scenario"][lang], "", f"**{r['question'][lang]}**", "", f"<details><summary>{L['ex']}</summary>", "",
            f"- **{L['assume']}**: {r['example']['assumptions'][lang]}", f"- **{L['steps']}**: {r['example']['steps'][lang]}",
            f"- **{L['alt']}**: {r['example']['alternative'][lang]}", "", "</details>", "",
            f"## {L['unc']}", "", obj["uncertainty_note"][lang], "", f"## {L['src']}", ""]
    out += [f"{i+1}. {s['citation']}" + (f" — <{s['url']}>" if web_url(s.get("url")) else "") for i, s in enumerate(obj["sources"])]
    out += ["", f"## {L['more']}", ""] + [(f"- [{m['title']}]({m['url']})" if web_url(m.get("url")) else f"- {m['title']}") + f" — {m['what'][lang]} ({m['access'][lang]})" for m in obj["further_reading"]]
    out += ["", "---", "", ("证据编号 [X-En] 对应同目录 evidence 文件中的逐字摘录。" if lang == "zh" else "Evidence ids [X-En] map to verbatim excerpts in the evidence file.")]
    return "\n".join(out) + "\n"

def _tag_maps() -> tuple[dict, dict]:
    """Theme tags and regions for the search index: config/edition_tags.json, config/regions.json, else the candidate file."""
    cfg = Path(__file__).resolve().parents[2] / "config"
    def load(name):
        p = cfg / name
        return {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")} if p.exists() else {}
    tags, regions = load("edition_tags.json"), load("regions.json")
    for c in sorted((cfg / "candidates").glob("*.json")) if (cfg / "candidates").exists() else []:
        try:
            j = json.loads(c.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if j.get("candidate_id") and j.get("tags") and j["candidate_id"] not in tags:
            tags[j["candidate_id"]] = j["tags"]
    return tags, regions


def search_index(objs) -> tuple[dict, dict]:
    """Reader search (2026-11-01), built with the site from PUBLISHED editions only: never samples, TEST editions,
    unscheduled inventory, evidence or review records. Two static files: search.json (title, dek, people, tags, book
    titles; loaded when the reader starts typing) and search_text.json (the article body, both languages; loaded on the
    first query). One entry per story; both languages in the same entry."""
    tags, regions = _tag_maps(); meta, text = [], []
    try:                                             # traditional names (吳起) also findable as typed (吴起)
        from .textnorm import t2s
    except Exception:
        t2s = lambda x: x
    both = lambda xs: list(dict.fromkeys(y for x in xs for y in (x, t2s(x)) if y))
    for o in objs:
        if o.get("status") in ("test", "reader_sample") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(o.get("edition_date", ""))):
            continue
        books = []
        if o.get("kind") == "excerpt":
            books += [o["work"]["title"], o["work"].get("author") or "", o["work"].get("author_zh") or ""]
        for x in list(o.get("sources") or []) + list(o.get("further_reading") or []):
            t = x.get("citation") or x.get("title") or ""
            books += re.findall(r"《([^》]{1,40})》", t) or ([t[:80]] if x.get("title") else [])
        y, m, d = o["edition_date"].split("-")
        meta.append({"id": o["edition_id"], "date": o["edition_date"], "category": o["category"], "title": o["title"], "dek": o["dek"],
                     "people": both(((o.get("episode") or {}).get("persons") or []) + [y for n in o.get("names") or [] for y in (n.get("zh"), n.get("orig")) if y]),
                     "tags": list(dict.fromkeys(list(tags.get(o["edition_id"]) or []) + ([regions[o["edition_id"]]] if regions.get(o["edition_id"]) else [])
                                                + list(CAT[o["category"]]))),
                     "books": both(b.strip() for b in books if b.strip()),
                     "minutes": o.get("reading_minutes"), "path": f"data/history/{y}/{m}/{d}-{o['edition_id']}.json"})
        paras = o["passage"] if o.get("kind") == "excerpt" else [p for s in o["sections"] for p in s["paras"]]
        text.append({"id": o["edition_id"], "zh": "\n".join(p["zh"] for p in paras), "en": "\n".join(p["en"] for p in paras)})
    meta.sort(key=lambda x: x["date"], reverse=True)
    return ({"schema": "history-search/v1", "items": meta}, {"schema": "history-search-text/v1", "items": text})


def build(objs, out: Path, base):
    (out/"email").mkdir(parents=True, exist_ok=True); (out/"site/history").mkdir(parents=True, exist_ok=True); (out/"site/data/history").mkdir(parents=True, exist_ok=True)
    index = []
    for o in objs:
        finalize(o)
        if o.get("status") == "reader_sample":
            # reader sample on the TEST preview: an admitted article shown before any schedule; listed as 样稿, never emailed
            public = {k: v for k, v in o.items() if k not in ("evidence_map", "preheader", "editor_log")}
            rel = f"data/history/samples/{o['edition_id']}.json"; p = out/"site"/rel; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(public, ensure_ascii=False, indent=1), encoding="utf-8")
            index.append({"edition_id": o["edition_id"], "revision": o["revision"], "edition_date": o["preview_date"], "category": o["category"],
                          "title": o["title"], "dek": o["dek"], "reading_minutes": o["reading_minutes"], "content_sha256": o["content_sha256"],
                          "path": rel, "sample": True, **({"kind": o["kind"]} if o.get("kind") else {})})
            continue
        (out/f"email/{o['edition_id']}.html").write_text(email_html(o, base), encoding="utf-8")
        (out/f"email/{o['edition_id']}.txt").write_text(email_text(o, base), encoding="utf-8")
        public = {k: v for k, v in o.items() if k not in ("evidence_map", "preheader", "editor_log")}
        prev_json = None
        if o.get("correction") and (o["correction"].get("previous") or {}).get("json"):
            public = json.loads(json.dumps(public)); prev_json = public["correction"]["previous"].pop("json")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(o.get("edition_date", ""))):
            # inventory not yet scheduled: preview JSON only, never listed in the public index
            p = out/f"site/data/history/unscheduled/{o['edition_id']}.json"; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(public, ensure_ascii=False, indent=1), encoding="utf-8"); continue
        y, m, d = o["edition_date"].split("-")
        p = out/f"site/data/history/{y}/{m}/{d}-{o['edition_id']}.json"; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(public, ensure_ascii=False, indent=1), encoding="utf-8")
        index.append({"edition_id": o["edition_id"], "revision": o["revision"], "edition_date": o["edition_date"], "category": o["category"],
                      "title": o["title"], "dek": o["dek"], "reading_minutes": o["reading_minutes"], "content_sha256": o["content_sha256"],
                      "path": f"data/history/{y}/{m}/{d}-{o['edition_id']}.json", **({"test": True} if o.get("status") == "test" else {}),
                      **({"kind": o["kind"]} if o.get("kind") else {}),
                      **({"corrected_at": o["correction"]["at"]} if o.get("correction") else {})})
        if prev_json is not None:                                     # the superseded revision stays published, byte for byte
            q = out/"site"/o["correction"]["previous"]["path"]; q.parent.mkdir(parents=True, exist_ok=True)
            q.write_text(prev_json, encoding="utf-8")
    index.sort(key=lambda x: x["edition_date"], reverse=True)
    (out/"site/data/history/index.json").write_text(json.dumps({"schema_version": "0.2", "items": index}, ensure_ascii=False, indent=1), encoding="utf-8")
    meta, text = search_index(objs)                  # rebuilt with every published issue (publish.commit_site -> site_export.export)
    (out/"site/data/history/search.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out/"site/data/history/search_text.json").write_text(json.dumps(text, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tpl = Path(__file__).with_name("templates")/"history_index.html"
    (out/"site/history/index.html").write_text(tpl.read_text(encoding="utf-8"), encoding="utf-8")

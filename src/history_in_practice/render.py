"""Render one bilingual content object to email HTML + text/plain, site data
JSON (+ index) and GitHub Markdown (zh/en). Stdlib only; every text field is
HTML-escaped; no model-produced HTML is ever emitted. All channels come from
the same object, so they share edition_id, revision and content_sha256."""
from __future__ import annotations
import hashlib, html, json, re, sys
from pathlib import Path

CAT = {"china_ancient": ("中国古代", "Ancient China"), "world": ("世界史", "World History"),
       "china_modern": ("中国近现代", "Modern China"), "us": ("美国史", "U.S. History")}
LBL = {"zh": dict(col="每日一鉴", today="今天可以怎么用", q="想一想", ex="一个参考思路", assume="假设", steps="可以怎么做",
                  alt="另一种合理选择", src="本篇依据", more="想再读一点", unc="出处与不确定性", min="分钟", read_web="在网页阅读",
                  read_en="Read in English", pause="想暂停接收？直接回复这封邮件写“暂停”，维护者会在配置中停发。", feedback="反馈：直接回复本邮件。",
                  edition="期次", stop="先停十秒，想想你会怎么做。"),
       "en": dict(col="History in Practice", today="Using it today", q="Think about it", ex="One possible approach", assume="Assumptions",
                  steps="What you could do", alt="Another reasonable choice", src="Sources", more="Read more",
                  unc="Sources and uncertainty", min="min", read_web="Read on the web", read_en="", pause="", feedback="", edition="Edition",
                  stop="Pause for ten seconds and decide what you would do.")}
ACCENT = "#7a5c3e"
ZH_CPM, EN_WPM = 320, 200   # reading-rate assumptions for the per-language estimate
e = lambda s: html.escape(s or "", quote=True)

def canonical(obj) -> str:
    keep = {k: obj[k] for k in ("edition_id","revision","title","dek","sections","reflection","uncertainty_note","sources","further_reading")}
    return json.dumps(keep, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def stats(obj):
    zh = en = 0
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
    obj["length"] = {"zh_chars": zh, "en_words": en, "basis": "body + question + example; excludes sources and read-more"}
    obj["reading_minutes"] = {"zh": max(1, round(zh / ZH_CPM)), "en": max(1, round(en / EN_WPM)),
                              "basis": f"estimate: {ZH_CPM} zh chars/min, {EN_WPM} en words/min"}
    obj["content_sha256"] = hashlib.sha256(canonical(obj).encode()).hexdigest()
    return obj

def link(obj, lang, base):
    return f"{base}/history/?story={obj['edition_id']}&lang={lang}"

# ---------------- email ----------------
def email_html(obj, base):
    def block(lang):
        L = LBL[lang]; out = []
        out.append(f'<h1 style="font-family:Georgia,\'Songti SC\',serif;font-size:26px;line-height:1.35;margin:8px 0 6px;color:#1d1d1f;">{e(obj["title"][lang])}</h1>')
        out.append(f'<p style="font-size:16px;line-height:1.7;color:#55524d;margin:0 0 18px;">{e(obj["dek"][lang])}</p>')
        for s in obj["sections"]:
            out.append(f'<h2 style="font-size:17px;color:{ACCENT};margin:26px 0 8px;letter-spacing:.02em;">{e(s["heading"][lang])}</h2>')
            for p in s["paras"]:
                style = "font-size:16px;line-height:1.85;margin:0 0 14px;color:#24221f;"
                if p["kind"] == "modern": style += "background:#f6f2ec;padding:10px 14px;border-radius:4px;"
                out.append(f'<p style="{style}">{e(p[lang])}</p>')
        r = obj["reflection"]
        out.append(f'<h2 style="font-size:17px;color:{ACCENT};margin:28px 0 8px;">{L["q"]}</h2>')
        out.append(f'<p style="font-size:16px;line-height:1.85;margin:0 0 10px;color:#24221f;">{e(r["scenario"][lang])}</p>')
        out.append(f'<p style="font-size:17px;line-height:1.8;margin:0 0 10px;font-weight:bold;color:#1d1d1f;border-left:3px solid {ACCENT};padding-left:12px;">{e(r["question"][lang])}</p>')
        out.append(f'<p style="font-size:14px;color:#8a857d;margin:0 0 30px;">{L["stop"]}</p>')
        out.append(f'<h3 style="font-size:15px;color:#55524d;margin:30px 0 8px;border-top:1px dashed #d8d2c8;padding-top:14px;">{L["ex"]}</h3>')
        sep = "：" if lang == "zh" else ": "
        for k, lab in (("assumptions", L["assume"]), ("steps", L["steps"]), ("alternative", L["alt"])):
            out.append(f'<p style="font-size:15px;line-height:1.8;margin:0 0 10px;color:#3a3732;"><b>{lab}{sep}</b>{e(r["example"][k][lang])}</p>')
        out.append(f'<h3 style="font-size:15px;color:#55524d;margin:24px 0 6px;">{L["unc"]}</h3><p style="font-size:14px;line-height:1.75;color:#55524d;margin:0 0 10px;">{e(obj["uncertainty_note"][lang])}</p>')
        out.append(f'<h3 style="font-size:15px;color:#55524d;margin:18px 0 6px;">{L["src"]}</h3><ol style="font-size:13px;line-height:1.7;color:#55524d;padding-left:20px;margin:0 0 12px;">')
        for s in obj["sources"]:
            a = ""
            if s.get("url"):
                a = ' · <a href="%s" style="color:%s;">%s</a>' % (e(s["url"]), ACCENT, e(s.get("link_label", "link")))
            out.append(f'<li>{e(s["citation"])}{a}</li>')
        out.append("</ol>")
        out.append(f'<h3 style="font-size:15px;color:#55524d;margin:18px 0 6px;">{L["more"]}</h3><ul style="font-size:13px;line-height:1.7;color:#55524d;padding-left:20px;margin:0;">')
        for m in obj["further_reading"]:
            out.append(f'<li><a href="{e(m["url"])}" style="color:{ACCENT};">{e(m["title"])}</a> — {e(m["what"][lang])} <span style="color:#8a857d;">({e(m["access"][lang])})</span></li>')
        out.append("</ul>")
        return "\n".join(out)
    cz, ce = CAT[obj["category"]]
    head = (f'<p style="font-size:13px;color:#8a857d;margin:0;letter-spacing:.04em;">{LBL["zh"]["col"]} · {e(obj["edition_date"])} · {cz} · '
            f'中文约 {obj["reading_minutes"]["zh"]} 分钟 · English ~{obj["reading_minutes"]["en"]} min（估算）</p>')
    btn = (f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:34px 0;"><tr>'
           f'<td style="background:{ACCENT};border-radius:4px;"><a href="{e(link(obj,"zh",base))}" style="display:inline-block;padding:10px 18px;color:#fff;text-decoration:none;font-size:15px;">{LBL["zh"]["read_web"]}</a></td>'
           f'<td style="width:10px;"></td><td style="border:1px solid {ACCENT};border-radius:4px;"><a href="{e(link(obj,"en",base))}" style="display:inline-block;padding:9px 18px;color:{ACCENT};text-decoration:none;font-size:15px;">Read in English</a></td></tr></table>'
           f'<hr style="border:none;border-top:1px solid #d8d2c8;margin:0 0 30px;">')
    foot = (f'<p style="font-size:12px;line-height:1.7;color:#8a857d;margin:36px 0 0;border-top:1px solid #e6e1d8;padding-top:14px;">'
            f'{LBL["zh"]["edition"]} {e(obj["edition_id"])} · rev {obj["revision"]} · {e(obj["edition_date"])} · '
            f'<a href="{e(link(obj,"zh",base))}" style="color:{ACCENT};">{e(link(obj,"zh",base))}</a><br>{LBL["zh"]["feedback"]} {LBL["zh"]["pause"]}</p>')
    pre = e(obj["preheader"]["zh"])
    return f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(obj["title"]["zh"])}</title></head>
<body style="margin:0;padding:0;background:#faf8f4;">
<div style="display:none;max-height:0;overflow:hidden;">{pre}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#faf8f4;"><tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border:1px solid #ece7de;">
<tr><td style="padding:28px 30px 34px;font-family:-apple-system,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',Helvetica,Arial,sans-serif;">
{head}
{block("zh")}
{btn}
<p style="font-size:13px;color:#8a857d;margin:0;letter-spacing:.04em;">{LBL["en"]["col"]} · {e(obj["edition_date"])} · {ce}</p>
{block("en")}
{foot}
</td></tr></table></td></tr></table></body></html>'''

def email_text(obj, base):
    def block(lang):
        L = LBL[lang]; r = obj["reflection"]; out = [obj["title"][lang], obj["dek"][lang], ""]
        for s in obj["sections"]:
            out += [f"== {s['heading'][lang]} ==", *[p[lang] + "\n" for p in s["paras"]]]
        out += [f"== {L['q']} ==", r["scenario"][lang], "", r["question"][lang], "", L["stop"], "", "-" * 20, f"{L['ex']}",
                f"{L['assume']}: {r['example']['assumptions'][lang]}", f"{L['steps']}: {r['example']['steps'][lang]}",
                f"{L['alt']}: {r['example']['alternative'][lang]}", "", f"== {L['unc']} ==", obj["uncertainty_note"][lang], "", f"== {L['src']} =="]
        out += [f"[{i+1}] {s['citation']} {s.get('url') or ''}".strip() for i, s in enumerate(obj["sources"])]
        out += ["", f"== {L['more']} =="] + [f"- {m['title']}: {m['what'][lang]} ({m['access'][lang]}) {m['url']}" for m in obj["further_reading"]]
        return "\n".join(out)
    return "\n".join([f"{LBL['zh']['col']} · {obj['edition_date']} · {CAT[obj['category']][0]}", "", block("zh"), "",
                      f"在网页阅读：{link(obj,'zh',base)}", f"Read in English: {link(obj,'en',base)}", "=" * 40, "", block("en"), "",
                      f"{obj['edition_id']} rev {obj['revision']} · {LBL['zh']['feedback']} {LBL['zh']['pause']}"])

def markdown(obj, lang):
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
    out += [f"{i+1}. {s['citation']}" + (f" — <{s['url']}>" if s.get("url") else "") for i, s in enumerate(obj["sources"])]
    out += ["", f"## {L['more']}", ""] + [f"- [{m['title']}]({m['url']}) — {m['what'][lang]} ({m['access'][lang]})" for m in obj["further_reading"]]
    out += ["", "---", "", ("证据编号 [X-En] 对应同目录 evidence 文件中的逐字摘录。" if lang == "zh" else "Evidence ids [X-En] map to verbatim excerpts in the evidence file.")]
    return "\n".join(out) + "\n"

def build(objs, out: Path, base):
    (out/"email").mkdir(parents=True, exist_ok=True); (out/"site/history").mkdir(parents=True, exist_ok=True)
    index = []
    for o in objs:
        finalize(o)
        (out/f"email/{o['edition_id']}.html").write_text(email_html(o, base), encoding="utf-8")
        (out/f"email/{o['edition_id']}.txt").write_text(email_text(o, base), encoding="utf-8")
        public = {k: v for k, v in o.items() if k not in ("evidence_map", "preheader", "editor_log")}
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(o.get("edition_date", ""))):
            # inventory not yet scheduled: preview JSON only, never listed in the public index
            p = out/f"site/data/history/unscheduled/{o['edition_id']}.json"; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(public, ensure_ascii=False, indent=1), encoding="utf-8"); continue
        y, m, d = o["edition_date"].split("-")
        p = out/f"site/data/history/{y}/{m}/{d}-{o['edition_id']}.json"; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(public, ensure_ascii=False, indent=1), encoding="utf-8")
        index.append({"edition_id": o["edition_id"], "revision": o["revision"], "edition_date": o["edition_date"], "category": o["category"],
                      "title": o["title"], "dek": o["dek"], "reading_minutes": o["reading_minutes"], "content_sha256": o["content_sha256"],
                      "path": f"data/history/{y}/{m}/{d}-{o['edition_id']}.json"})
    index.sort(key=lambda x: x["edition_date"], reverse=True)
    (out/"site/data/history/index.json").write_text(json.dumps({"schema_version": "0.2", "items": index}, ensure_ascii=False, indent=1), encoding="utf-8")
    tpl = Path(__file__).with_name("templates")/"history_index.html"
    (out/"site/history/index.html").write_text(tpl.read_text(encoding="utf-8"), encoding="utf-8")

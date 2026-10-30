"""Deterministic checks for one final bilingual content object.
Run with a python that has `opencc`. Exit 1 on any BLOCK finding.
These checks prove structure and quote/evidence consistency only; they do
not prove that the history is true."""
import json, re, sys
from pathlib import Path
from .textnorm import t2s
SECTIONS = ["hook", "context", "story", "analysis", "today", "limits"]
CN_NUM = {"零":0,"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9}

def cn_to_int(s):
    total, sec, num = 0, 0, 0
    for ch in s:
        if ch in CN_NUM: num = CN_NUM[ch]
        elif ch == "十": sec += (num or 1) * 10; num = 0
        elif ch == "百": sec += num * 100; num = 0
        elif ch == "千": sec += num * 1000; num = 0
        elif ch == "万": total += (sec + num) * 10000; sec = num = 0
    return total + sec + num


EN_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
EN_TENS = {"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60,"seventy":70,"eighty":80,"ninety":90}
def en_number_words(text):
    """Parse runs like 'forty thousand', 'five hundred and thirty-five'; keep values >= 10."""
    out = set(); toks = re.findall(r"[a-z]+", text.lower().replace("-", " "))
    cur = total = 0; active = False
    for w in toks + ["."]:
        if w in EN_UNITS: cur += EN_UNITS[w]; active = True
        elif w in EN_TENS: cur += EN_TENS[w]; active = True
        elif w == "hundred" and active: cur *= 100
        elif w == "thousand" and active: total += cur * 1000; cur = 0
        elif w == "and" and active: continue
        else:
            if active and total + cur >= 10: out.add(total + cur)
            cur = total = 0; active = False
    return out

def numbers(text, lang):
    if lang == "zh":
        text = re.sub(r"\d+(?=月)", "", text)          # month numbers have no English digit
        text = re.sub(r"(?<![一二两三四五六七八九])十(?=[天日年人])", "十十", text)  # lone 十 -> parse as 10
    else:
        text = re.sub(r"\ba hundred\b", "one hundred", text, flags=re.I)
    ns = {int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", text)}
    if lang == "zh":
        ns |= {cn_to_int(m) for m in re.findall(r"[一二两三四五六七八九十百千万]{2,}", text.replace("十十", "")) if cn_to_int(m) >= 10} | ({10} if "十十" in text else set())
    else:
        ns |= en_number_words(text)
    return ns

def check(o: dict, ev: dict):
    """Return (findings, stats); findings are (level, message), level in BLOCK|FIX|CHECK."""
    ex = {e["id"]: e for e in ev["excerpts"]}
    find = []  # (level, msg)
    ids = [s["id"] for s in o["sections"]]
    if ids != SECTIONS: find.append(("BLOCK", f"section ids {ids} != {SECTIONS}"))
    today = next((s for s in o["sections"] if s["id"] == "today"), None)
    if today and len(today["paras"]) != 2: find.append(("FIX", "today should have exactly two applications"))
    for s in o["sections"]:
        for i, p in enumerate(s["paras"]):
            where = f"{s['id']}[{i}]"
            for lang in ("zh", "en"):
                if not p.get(lang, "").strip(): find.append(("BLOCK", f"{where} missing {lang}"))
                if re.search(r"<[a-zA-Z/][^>]*>", p.get(lang, "")): find.append(("BLOCK", f"{where} contains markup"))
            if p["kind"] == "record" and not p["ev"]: find.append(("BLOCK", f"{where} record paragraph without evidence"))
            for x in p["ev"]:
                if x not in ex: find.append(("BLOCK", f"{where} unknown evidence id {x}"))
            if p["kind"] == "modern" and p["ev"]: find.append(("FIX", f"{where} modern scene cites evidence"))
            # quotes: classical Chinese in 「」 must occur (t2s) in a cited excerpt
            for q in re.findall(r"「([^」]{2,})」", p["zh"]):
                pool = "".join(t2s(ex[x]["display"]) for x in p["ev"] if x in ex)
                if re.search(r"[一-鿿]", q) and t2s(q).replace("，", "").replace("。", "") not in pool.replace("，", "").replace("。", "") \
                   and not q.startswith("译"):
                    find.append(("BLOCK", f"{where} zh quote not in cited evidence: 「{q}」"))
            # quotes: English quotations in “ ” must be verbatim in a cited English excerpt
            pool_en = " ".join(re.sub(r"\s+", " ", ex[x]["display"]).replace("’", "'") for x in p["ev"] if x in ex)
            for q in re.findall(r"“([^”]{12,})”", p["en"]) + re.findall(r'"([^"]{12,})"', p["en"]):
                qn = re.sub(r"\s+", " ", q).replace("’", "'").rstrip(".,")
                if re.search(r"[A-Za-z]", pool_en) and qn not in pool_en:
                    find.append(("BLOCK", f"{where} en quote not verbatim in cited evidence: “{q[:70]}”"))
            nz, ne = numbers(p["zh"], "zh"), numbers(p["en"], "en")
            if nz ^ ne: find.append(("CHECK", f"{where} numbers differ zh{sorted(nz)} en{sorted(ne)}"))
            en_digits = {int(x.replace(",", "")) for x in re.findall(r"\b\d[\d,]*\b", p["en"])}
            drift = {x for x in en_digits - nz if x >= 10 and str(x) not in p["zh"]}
            if drift: find.append(("BLOCK", f"{where} English has number(s) {sorted(drift)} not present in Chinese"))
    r = o["reflection"]
    if today:   # editorial: the model tends to reuse the open question's scenario as a "today" example
        from .registry import bigrams
        sc = set(bigrams(r["scenario"]["zh"] + r["question"]["zh"]).split())
        for i, p in enumerate(today["paras"]):
            pb = set(bigrams(p["zh"]).split())
            if pb and len(pb & sc) / max(1, min(len(pb), len(sc))) >= 0.12:
                find.append(("FIX", f"today[{i}] may repeat the open-question scenario"))
    for k in ("scenario", "question"):
        for lang in ("zh", "en"):
            if not r[k][lang].strip(): find.append(("BLOCK", f"reflection.{k}.{lang} empty"))
    for k in ("assumptions", "steps", "alternative"):
        for lang in ("zh", "en"):
            if not r["example"][k][lang].strip(): find.append(("BLOCK", f"reflection.example.{k}.{lang} empty"))
    if not o.get("sources") or len({s.get("basis") for s in o["sources"]}) < 2 and not o.get("single_basis_disclosed"):
        find.append(("BLOCK", "fewer than two source bases and no single-basis disclosure"))
    for m in o.get("further_reading", []):
        if not m.get("what", {}).get("zh") or not m.get("access", {}).get("zh"): find.append(("FIX", f"read-more item lacks description: {m.get('title')}"))
    zh = sum(len(re.findall(r"[一-鿿]", p["zh"])) for s in o["sections"] for p in s["paras"])
    en = sum(len(re.findall(r"[A-Za-z']+", p["en"])) for s in o["sections"] for p in s["paras"])
    return find, {"body_zh_chars": zh, "body_en_words": en}


def blocked(findings) -> bool:
    return any(level == "BLOCK" for level, _ in findings)

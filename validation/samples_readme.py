"""Generate samples/README.md tables from the article files and timing logs."""
import json, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import render, checks
ROOT = Path(__file__).resolve().parents[1]
CAT = {"china_ancient": "中国古代", "world": "世界史", "china_modern": "中国近现代", "us": "美国史"}

def timings(files):
    out = []
    for f in files:
        p = ROOT / f
        if p.exists():
            out += json.loads(p.read_text())
    return out

def main():
    t1 = timings(["samples/model_timings.json"]); t2 = timings(["samples/model_timings_v2.json"]); t3 = timings(["samples/model_timings_v3.json"])
    rows, trows = [], []
    for s in "ABCDE":
        o = json.loads((ROOT / f"samples/{s}/article.json").read_text()); render.finalize(o)
        ev = json.loads((ROOT / f"samples/evidence_{s}.json").read_text())
        f, _ = checks.check(o, ev)
        edits = json.loads((ROOT / f"samples/{s}/editor_log_v2.json").read_text()) if (ROOT / f"samples/{s}/editor_log_v2.json").exists() else []
        html = (ROOT / f"samples/preview/email/{o['edition_id']}.html")
        bases = sorted({x.get("basis") for x in o["sources"] if x.get("basis") and not str(x.get("basis")).endswith("-derived")})
        who = "（Claude 撰写，非 Hermes 生成）" if o.get("authorship") else ""
        rows.append(f"| [{s}]({s}/article.zh.md) · [EN]({s}/article.en.md) | {CAT[o['category']]} | {o['title']['zh']}{who} | {o['reflection']['type']} | "
                    f"{o['length']['zh_chars']} 字 · 约 {o['reading_minutes']['zh']} 分钟 | {o['length']['en_words']} words · ~{o['reading_minutes']['en']} min | "
                    f"{len(ev['excerpts'])} / {len(bases)} | {html.stat().st_size // 1024 if html.exists() else '-'} KB | "
                    f"{sum(1 for l, _ in f if l == 'BLOCK')} | {max(0, len(edits) - 1)} |")
        def tot(t): return round(sum(x["wall_s"] for x in t if x.get("story") == s))
        steps = [x for x in t2 + t3 if x.get("story") == s]
        if s == "E":
            trows.append("| E | — | provider refused (MiMo: “rejected because it was considered high risk”, 2 calls × ~6 s); written by Claude from the evidence pack | — |"); continue
        trows.append(f"| {s} | {tot(t1)} s | " + " · ".join(f"{x['step']} {x['wall_s']:.0f}s ({x['prompt_bytes']//1024}→{x['out_bytes']//1024} KB{'' if x.get('json_ok') else ', invalid JSON'})" for x in steps) + f" | {tot(t2) + tot(t3)} s |")
    return rows, trows

if __name__ == "__main__":
    r, t = main(); print("\n".join(r)); print(); print("\n".join(t))


def auto_rows():
    """Automated candidates that went through the pipeline and an editor pass (samples/auto/<cid>/)."""
    out = []
    for d in sorted((ROOT / "samples/auto").glob("cand-*/article.json")):
        o = json.loads(d.read_text()); render.finalize(o); ev = json.loads((d.parent / "evidence.json").read_text())
        f, _ = checks.check(o, ev)
        log = json.loads((d.parent / "editor_log.json").read_text()) if (d.parent / "editor_log.json").exists() else []
        rep = json.loads((d.parent / "model_report.json").read_text()) if (d.parent / "model_report.json").exists() else {}
        cid = d.parent.name; outcome = rep.get("outcome", "-")
        rv = json.loads((d.parent / "model_review_zh.json").read_text()) if (d.parent / "model_review_zh.json").exists() else {}
        n_fix = sum(1 for i in rv.get("issues", []) if i.get("severity") in ("fix", "block"))
        if outcome == "checked" and n_fix:      # judged by the pre-rule code in queue 2
            outcome = f"checked（旧规则；审稿 {n_fix} 条 fix，按现行规则为 pending_review，已重排）"
        er = json.loads((d.parent / "editor_record.json").read_text()) if (d.parent / "editor_record.json").exists() else {}
        now = ("已入库（编辑记录绑定最终正文）" if er.get("outcome") == "admissible" else
               f"待处理：{len(er.get('remaining', []))} 个未解决问题" if er else "（无编辑记录）")
        nedits = len(log) + sum(x.get("edits_total", 0) for x in [er])
        out.append(f"| [{cid.replace('cand-20261030-', '').replace('cand-auto-20261030-', 'auto: ')}](auto/{cid}/article.zh.md) · [EN](auto/{cid}/article.en.md) | {CAT[o['category']]} | {o['title']['zh']} | "
                   f"{o['length']['zh_chars']} 字 · 约 {o['reading_minutes']['zh']} 分钟 | {o['length']['en_words']} words · ~{o['reading_minutes']['en']} min | "
                   f"{len(ev['excerpts'])} | {outcome} | {nedits} | **{now}** |")
    return out


def write():
    rows, trows = main(); arows = auto_rows()
    text = f"""# 双语样稿与自动供稿文章（2026-10-30 overnight）

用户最新目标：**中文完整阅读约十分钟，英文完整阅读也约十分钟**（不是双语合计）。本目录有五篇样稿（A–D 由 Hermes 起草、经编辑修改；E 因模型服务拒绝而由 Claude 撰写）和七篇自动供稿文章（`auto/`），附证据映射、开放问题与示例、延伸阅读，以及邮件与网页本地预览。样稿是**样稿，不是正式期次**（`status: sample`），自动供稿文章在库存中、未排期；都未发布、未发信，样稿日期是假定排期。

## 一览

| 样稿 | 类别 | 标题 | 问题类型 | 中文（含问题与示例） | 英文（含问题与示例） | 摘录 / 独立来源基础 | 邮件 HTML | BLOCK | 本版编辑修改 |
|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

- 阅读时间是估算：中文 320 字/分、英文 200 词/分，均不含出处与延伸阅读。
- 中文五篇样稿都在 2,500–2,700 字，比 2,800 字的参考下限略短，约 8 分钟。按要求没有为凑字数扩写；若两位读者实读明显短于十分钟，再补有依据的背景。
- 英文 B、C、D 约 10–11 分钟。A 的英文偏长（约 13 分钟），已排入一次“只压缩措辞、不删事实”的模型精简；结果见 `docs/OVERNIGHT_REPORT.md`。
- A 只有一个来源基础：《史记》系统，《汉书》据其改写；文中已披露。C 的美国教育者抗议信只见于容闳书中转载，文中已注明。

## 自动供稿文章与当前状态

`hip prepare-queue` 跑出的候选，经编辑阶段处理。“模型结果”是流水线本身的结论；“当前状态”取自最新一次编辑记录（`editor_record.json`）：只有最终正文经过绑定的复审与英文一致性检查、没有剩余问题，才算入库。2026-10-30 稳定化后，夜里人工编辑入库的七篇都重新复审，详见 `docs/STABILIZATION_REPORT.md`。

| 候选 | 类别 | 标题 | 中文 | 英文 | 摘录 | 模型结果 | 编辑修改（人工 + 最近一次自动） | 当前状态 |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(arows)}

- 编辑修改数包含整段重写（记为一条，前后全文都在 `editor_log.json`）。
- 最初的候选证据包只有 8–10 条摘录，初稿只有 6–7 分钟；从同一批已缓存的来源补足摘录后，重写到 9 分钟左右。之后的候选（廉蔺、富兰克林、达尔文与华莱士）在跑模型前就补足了摘录。

## 怎么做的（真实运行，不是手写冒充自动化）

1. **第一版**：短篇，见 git 历史 `831f8e6`。
2. **补证据**：从同一批已取回的来源再截取有记录的背景与过程。四篇共 80 条逐字摘录，全部由起止锚点从缓存文本机械截取（`validation/build_evidence.py`）。
3. **模型三步**：经项目级隔离调用器（0 工具、无 SOUL/memory/AGENTS 注入）调用 Hermes / mimo-v2.6-pro，依次为扩写中文、按证据审稿、写自然英文版；原始输出在 `X/model_runs/`。
4. **编辑修改**：Claude（Opus）对照审稿意见与证据逐条修改，记录在 `X/editor_log_v2.json`，每条有修改前后与理由。多数是收紧事实与引语；有几处是证据包截短，处理方式是扩充摘录，而不是删掉正确内容。
5. **程序检查**：四篇均无 BLOCK/FIX。古文引语按繁简对照、英文引语逐字对照所引摘录；英文出现中文没有的数字即 BLOCK；“今天可以怎么用”与开放问题场景重复会提示 FIX。
6. **渲染**：同一对象生成邮件 HTML/纯文本/.eml（虚构收件人）、网页数据、GitHub Markdown；`content_sha256` 覆盖双语正文、问题、示例与来源。

### 模型耗时（第二版）

| 样稿 | 第一版三步 | 第二版各步（输入→输出） | 第二版合计 |
|---|---|---|---|
{chr(10).join(trows)}

无效 JSON 都没有手工修 JSON：两次是括号错位，靠自动重试解决；一次是结尾多余逗号，靠解析回退修复。

## 文件

| 文件 | 内容 |
|---|---|
| `X/article.json` | 正式内容对象（双语、每段 `kind` 与证据 ID、来源、延伸阅读、`episode`、`content_sha256`） |
| `X/article.zh.md` · `X/article.en.md` | GitHub 可读版本，段尾 `[X-En]` 是证据编号 |
| `evidence_X.json` | 逐字摘录、位置、偏移、来源取回时间与 SHA-256 |
| `briefs/` · `briefs_v2/` | 编辑简报：只列有记录的骨架、必须披露的不确定性 |
| `X/model_runs/` | Hermes 原始输出 |
| `X/edits_v2.json` · `X/editor_log_v2.json` | 编辑修改 |
| `preview/email/` | 邮件 HTML、纯文本、`.eml` |
| `preview/site/` | 网页预览（`history/index.html` + `data/history/`） |
| `preview/screenshots/` | 无头 Firefox 截图 |

## 本地预览

```bash
cd /home/star/history-in-practice
python3 -I validation/preview_server.py 18767 samples/preview/site     # 只绑定 127.0.0.1；8765 已被本机其他服务占用
# 打开 http://127.0.0.1:18767/history/  或  /history/?story=sample-B&lang=en
```

## 读者反馈请看

1. 中文、英文各自实际读完用了几分钟。
2. 开头是否想继续读，哪里开始走神。
3. 英文读起来是否自然。
4. 开放问题是否真有不同答案。
5. 哪个细节最记得住。
"""
    (ROOT / "samples/README.md").write_text(text, encoding="utf-8")

if __name__ == "__main__" and "--write" in sys.argv:
    write()

# 双语样稿与自动供稿文章（2026-10-30 overnight）

用户最新目标：**中文完整阅读约十分钟，英文完整阅读也约十分钟**（不是双语合计）。本目录有五篇样稿（A–D 由 Hermes 起草、经编辑修改；E 因模型服务拒绝而由 Claude 撰写）和七篇自动供稿文章（`auto/`），附证据映射、开放问题与示例、延伸阅读，以及邮件与网页本地预览。样稿是**样稿，不是正式期次**（`status: sample`），自动供稿文章在库存中、未排期；都未发布、未发信，样稿日期是假定排期。

## 一览

| 样稿 | 类别 | 标题 | 问题类型 | 中文（含问题与示例） | 英文（含问题与示例） | 摘录 / 独立来源基础 | 邮件 HTML | BLOCK | 本版编辑修改 |
|---|---|---|---|---|---|---|---|---|---|
| [A](A/article.zh.md) · [EN](A/article.en.md) | 中国古代 | 韩信、陈平、范增：项羽留不住的三个人 | 何时离开 | 2673 字 · 约 8 分钟 | 2682 words · ~13 min | 20 / 1 | 41 KB | 0 | 16 |
| [B](B/article.zh.md) · [EN](B/article.en.md) | 世界史 | 拆掉水泵把手，宽街的霍乱就停了吗？ | 如何纠错 | 2668 字 · 约 8 分钟 | 2272 words · ~11 min | 20 / 2 | 37 KB | 0 | 23 |
| [C](C/article.zh.md) · [EN](C/article.en.md) | 中国近现代 | 快要毕业时，一百个留学生被叫回国 | 不确定下决策（项目中途如何评估） | 2534 字 · 约 8 分钟 | 2192 words · ~11 min | 23 / 3 | 39 KB | 0 | 17 |
| [D](D/article.zh.md) · [EN](D/article.en.md) | 美国史 | 欠饷是真的，匿名信也是真的：华盛顿在纽堡站在哪里 | 如何传达坏消息 | 2554 字 · 约 8 分钟 | 2002 words · ~10 min | 17 / 3 | 36 KB | 0 | 14 |
| [E](E/article.zh.md) · [EN](E/article.en.md) | 中国近现代 | 没有调查，没有发言权：这句话原本要求什么（Claude 撰写，非 Hermes 生成） | 相信谁 | 2605 字 · 约 8 分钟 | 1898 words · ~9 min | 24 / 1 | 34 KB | 0 | 0 |

- 阅读时间是估算：中文 320 字/分、英文 200 词/分，均不含出处与延伸阅读。
- 中文五篇样稿都在 2,500–2,700 字，比 2,800 字的参考下限略短，约 8 分钟。按要求没有为凑字数扩写；若两位读者实读明显短于十分钟，再补有依据的背景。
- 英文 B、C、D 约 10–11 分钟。A 的英文偏长（约 13 分钟），已排入一次“只压缩措辞、不删事实”的模型精简；结果见 `docs/OVERNIGHT_REPORT.md`。
- A 只有一个来源基础：《史记》系统，《汉书》据其改写；文中已披露。C 的美国教育者抗议信只见于容闳书中转载，文中已注明。

## 自动供稿：进入库存的文章

`hip prepare-queue` 跑出的候选，经编辑修改后用 `hip admit --from-pending` 进入库存（未排期、未发布）。“模型结果”是自动流程本身给出的结论；`pending_review` 表示按规则不能直接入库，必须人工改。

| 候选 | 类别 | 标题 | 中文 | 英文 | 摘录 | 模型结果 | 编辑修改 | BLOCK/FIX |
|---|---|---|---|---|---|---|---|---|
| [darwin-wallace](auto/cand-20261030-darwin-wallace/article.zh.md) · [EN](auto/cand-20261030-darwin-wallace/article.en.md) | 世界史 | 同一个想法，两份手稿：1858年林奈学会的一次安排 | 2546 字 · 约 8 分钟 | 1886 words · ~9 min | 22 | pending_review | 10 | 0 |
| [franklin-1787](auto/cand-20261030-franklin-1787/article.zh.md) · [EN](auto/cand-20261030-franklin-1787/article.en.md) | 美国史 | 看不出是升是落：1787年9月17日，签字前的最后一讲 | 3107 字 · 约 10 分钟 | 2279 words · ~11 min | 24 | pending_review | 12 | 0 |
| [jingxing](auto/cand-20261030-jingxing/article.zh.md) · [EN](auto/cand-20261030-jingxing/article.en.md) | 中国古代 | 井陉口前，那条没人听的计 | 2863 字 · 约 9 分钟 | 2385 words · ~12 min | 10 | pending_review | 30 | 0 |
| [lian-lin](auto/cand-20261030-lian-lin/article.zh.md) · [EN](auto/cand-20261030-lian-lin/article.en.md) | 中国古代 | 位次之争：廉颇的委屈与那根荆条 | 2859 字 · 约 9 分钟 | 2500 words · ~12 min | 17 | pending_review | 34 | 0 |
| [shackleton-ocean-camp](auto/cand-20261030-shackleton-ocean-camp/article.zh.md) · [EN](auto/cand-20261030-shackleton-ocean-camp/article.en.md) | 世界史 | 走六英里，进一英里 | 2837 字 · 约 9 分钟 | 2279 words · ~11 min | 18 | checked（旧规则；审稿 11 条 fix，按现行规则为 pending_review，已重排） | 39 | 0 |
| [snow-water-companies](auto/cand-20261030-snow-water-companies/article.zh.md) · [EN](auto/cand-20261030-snow-water-companies/article.en.md) | 世界史 | 同一条街上的两根水管 | 3012 字 · 约 9 分钟 | 2232 words · ~11 min | 12 | checked（旧规则；审稿 13 条 fix，按现行规则为 pending_review，已重排） | 14 | 0 |
| [washington-resigns](auto/cand-20261030-washington-resigns/article.zh.md) · [EN](auto/cand-20261030-washington-resigns/article.en.md) | 美国史 | 鞠躬的人与脱帽的人：1783年的一次权力交还 | 2936 字 · 约 9 分钟 | 2424 words · ~12 min | 18 | pending_review | 33 | 0 |

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
| A | 602 s | 4_expand_zh 224s (21→15 KB) · 5_review_zh 254s (24→3 KB) · 6_en_long 242s (25→17 KB) · 7_en_tight 1139s (27→0 KB, invalid JSON) | 1860 s |
| B | 601 s | 4_expand_zh 156s (24→12 KB) · 5_review_zh 171s (25→5 KB) · 6_en_long 141s (26→16 KB, invalid JSON) · 6b_en_long_retry 202s (26→16 KB, invalid JSON) | 670 s |
| C | 554 s | 4_expand_zh 245s (24→12 KB) · 5_review_zh 220s (24→6 KB) · 6_en_long 203s (25→16 KB) | 668 s |
| D | 447 s | 4_expand_zh 217s (20→12 KB, invalid JSON) · 4b_expand_zh_retry 111s (21→13 KB) · 5_review_zh 135s (23→4 KB) · 6_en_long 149s (24→16 KB) | 612 s |
| E | — | provider refused (MiMo: “rejected because it was considered high risk”, 2 calls × ~6 s); written by Claude from the evidence pack | — |

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

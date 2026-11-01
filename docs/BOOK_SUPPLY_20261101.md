# E-book library → continuous nightly supply (2026-11-01)

**Branch:** `feature/book-supply`. Worktree `~/hip-wt-books`, with its own data directory (a copy of the state DB, source cache and book files). The launched daily job (`main` in `~/history-in-practice`) was not touched: its timers, recipients and schedule are unchanged.

**Model:** every model call went to Claude Opus (`claude-opus-5-5`) through the Claude Code CLI on the claude.ai subscription. No paid API; no MiMo.

## 1. What counts as a book (levels)

`config/books/library.json` is public metadata only. Files, parsed text and caches stay on the Pi under `data/books` and `data/source_cache`.

| Level | Meaning | Now |
|---|---|---|
| catalogued | listed in a saved repository tree or catalogue only | **1,270** book-like files in the saved trees (HarborLibrary ×9, two forks, Markdown repos), plus the Drive listing. Leads, not books |
| acquired | the file is on the Pi: pinned repository commit + path, git blob verified, sha256 | 13 |
| readable | parsed text: TXT/EPUB, or a PDF with a real text layer (scans refused) | (all 6 of the first batch passed and moved on to usable) |
| usable | ingested with chapter units; in the nightly pool | **6 books, 153 units** |
| unsuitable | with a reason | the novelised Markdown 《明朝那些事儿》 (discovery only, never evidence) |

**First batch:**

| Book | Format | Category | Paragraphs / units | Units tried | Candidates |
|---|---|---|---|---|---|
| 孔飞力《叫魂：1768年中国妖术大恐慌》（陈兼、刘昶 译） | TXT, HarborLibrary/Chinese-History | 中国古代 · 社会/政治 | 216 / 16 | 2 | 1 |
| 唐德刚《晚清七十年》 | EPUB, HarborLibrary/Chinese-History | 中国近现代 · 政治/人物 | 3,751 / 46 | 2 | 1 |
| 梁启超《李鸿章传》(1901) | EPUB, zh.wikisource export | 中国近现代 · 传记/外交 | 756 / 10 | 5 | 2 |
| 温功义《三案始末》（三联 2013） | PDF (text layer), bo-guan-yue-qu | 中国古代 · 宫廷政治 | 456 / 8 | 2 | 2 |
| 《中国财政史十六讲》 | PDF (text layer), bo-guan-yue-qu | 中国古代/近现代 · 财政 | 2,761 / 57 | 5 | 1 |
| 达娃·索贝尔《经度》（肖明波 译） | PDF (text layer), bo-guan-yue-qu | 世界 · 科学 | 674 / 17 | 2 | 1 |

**Notes on the batch:**
- 《叫魂》 and 《晚清七十年》 were newly fetched this round: one file each, from the pinned HarborLibrary commit, blob verified.
- The three PDFs were checked for a real text layer: CJK share 0.79–0.88, no junk.
- The 财政史 PDF does not name its author in the text layer (it presents itself as a 上海财经大学 textbook). The author is recorded as unverified rather than guessed. It is the low-yield book: theory chapters are skipped.

**Acquired, not ingested this round** (alternates): 黄仁宇《赫逊河畔谈中国历史》, 钱穆《中国历代政治得失》, Mackay, Shoe Dog, The Worlds I See, Curie. 《胡适口述自传》 is excluded for now (owner).

**Google Drive** is a later source: the listing exists, but the download path was not connected this round.

## 2. From a book to a candidate

1. **Units.** `library.ingest` writes the book into the source cache with a location map and cuts chapter-sized units over the normalised text:
   - small sections are merged and long chapters split;
   - front matter (目录, 序, 索引…) is left out;
   - units about people paused by the owner (胡适, 吴起) are skipped.
2. **Picking.** The nightly picker (`supply.pick_entry`) offers **books first**: an untried unit of a usable book in the category the mix needs, from the least-used book, in a stable spread order through the book. The original catalogue (Wikisource etc.) is the fallback. No fixed book quota.
3. **Proposal.** Claude reads the whole unit (≤14,000 characters) with `prompts/propose_book.md`, in addition to the usual proposal rules. It must either:
   - pick **one complete episode**, where the cause, the course and the **outcome** all have excerpts in the unit and a core excerpt sits on the outcome; or
   - answer `skip` with a reason. The skip is logged and the unit counts as tried.
4. **Voices.** Each excerpt is labelled 【当事人】 (quoted participant: rescripts, letters, memorials), 【作者】, 【译注】 or 【后世评论】. 【文学化】 passages are dropped mechanically and never become evidence; an unlabelled excerpt is also dropped.
5. **Mechanical checks** (unchanged): anchors verbatim and unique, no overlap with passages used by registered episodes, at least 12 excerpts, core excerpts survive, and an **event-level dedupe** (registry: same people/place/time/action, or the same source passage).
6. **Candidate provenance:**
   - book title, author, translator, edition, repository + pinned commit + path, git blob, file sha256;
   - the unit (chapter title, offsets, first location);
   - for every excerpt: its voice and **book location** (EPUB spine + paragraph; PDF page + paragraph; TXT offset in the normalised text, with its sha256).
7. **Downstream, unchanged:** pre-draft source-context review (it reads around the excerpts), Claude draft / review / English, the final editor, the post-draft source-context review, admission.

**Source record.** Every attempt logs `source_kind` (book | catalogue), book, unit and outcome (`data/supply/attempts.jsonl`). The units tried in this validation are in the tracked ledger `config/books/attempts.jsonl`, so production does not repeat them.

## 3. Candidates proposed automatically from the imported books (this run)

22 units tried; 8 candidates; 14 skipped. Each skip has a stated reason, e.g. "本章是盛世经济与社会背景的概论…没有结局".

| Candidate | Episode | Book · location |
|---|---|---|
| `bk-jiaohun-u14-1` | 江西巡抚吴绍诗（“老菩萨”）在全国搜捕“叫魂”时一个人也没抓，次年升任刑部尚书 (1768–69) | 《叫魂》第九章 · TXT offset 150234+ |
| `bk-sanan-u4-1` | 万历病中口授废矿税遗诏，病好后连夜索回；首辅沈一贯给还是不给 (1602) | 《三案始末》PDF p.78– |
| `bk-sanan-u7-1` | 崇祯三次退回附逆名单，亲定《钦定逆案》262人 (1628–29) | 《三案始末》PDF p.134– |
| `bk-lhzz-u1-1` | 苏州降约：程学启许官、戈登作保，李鸿章设宴杀降 (1863–64) | 《李鸿章传》第三、四章 · EPUB spine 5– |
| `bk-lhzz-u5-1` | 马关遇刺后不取子弹，带伤谈判 (1895) | 《李鸿章传》第八章 · EPUB spine 10 |
| `bk-wq70-u22-1` | 李鸿章保举醇亲王掌海军衙门，此后对挪用海军经费一再退让 (1884–94) | 《晚清七十年》【三】二 · EPUB spine 22 |
| `bk-czs16-u27-1` | 王安石“候法已成即逐之”：先用能办事的人，后来换不掉 (1069–76) | 《中国财政史十六讲》PDF p.250– |
| `bk-jingdu-u14-1` | 经度局面对阿诺德与厄恩肖的擒纵器发明权之争，各颁3000英镑 (1782–1805) | 《经度》第十四章 · PDF p.112– |

## 4. Two articles through the normal chain

(see section 4 results below)

## 5. How the nightly job keeps supplying

**No new timer.** `hip-prepare` (10:00 Beijing) already runs `hip nightly`. When fewer than 2 unprocessed candidates are waiting, it proposes for the categories the mix needs most; `pick_entry` now offers book units first. Then it drafts (at most 2 articles per batch) and runs the final editor.

**Pool size.** 153 units in 6 books. At today's yield of about one candidate per three units, that is roughly 50 candidates before new books are needed. Adding a book:
1. add its library.json entry: repository, commit, path, metadata, categories;
2. run `hip library ingest --book ID` (or `--book all`).

## 6. Deployment (after merging; nothing else changes)

1. Merge `feature/book-supply` into `main`. On the Pi: `cd ~/history-in-practice && git pull --ff-only`.
2. Run `bin/hip library ingest --book all`. It:
   - fetches the two new files (叫魂, 晚清七十年) from their pinned commits, blob verified;
   - ingests the six books into the production data directory;
   - prints each book's level and unit count.
3. No change to timers, recipients or the send schedule. The next `hip-prepare` run draws from the books.

**Rollback:** set the books' level back in library.json, or revert the merge. The picker then uses the catalogue only.

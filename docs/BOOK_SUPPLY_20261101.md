# E-book library → continuous nightly supply (2026-11-01)

**Branch:** `feature/book-supply`. Worktree `~/hip-wt-books`, with its own data directory (a copy of the state DB, source cache and book files). The launched daily job (`main` in `~/history-in-practice`) was not touched: its timers, recipients and schedule are unchanged.

**Model:** every model call went to Claude Opus (`claude-opus-5-5`) through the Claude Code CLI on the claude.ai subscription. No paid API; no MiMo.

## 1. What counts as a book (levels)

`config/books/library.json` is public metadata only. Files, parsed text and caches stay on the Pi under `data/books` and `data/source_cache`.

| Level | Meaning | Now |
|---|---|---|
| catalogued | listed in a saved repository tree or catalogue only | **1,270** book-like files in the saved trees (HarborLibrary ×9, two forks, Markdown repos), plus the Drive listing. Leads, not books |
| acquired | the file is on the Pi: pinned repository commit + path, git blob verified, sha256 | 13 |
| readable | parsed text: TXT/EPUB, or a PDF with a real text layer (scans refused) | 5 alternates (below), checked, not yet in the pool |
| usable | ingested with chapter units; in the nightly pool | **8 books, 233 units** (the first batch of 6, plus Mackay and Shoe Dog) |
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

**Also usable** (ingested after the first batch, so that the 世界 and 美国 categories have books too): Charles Mackay, *Extraordinary Popular Delusions and the Madness of Crowds* (EPUB, Project Gutenberg; 世界; 54 units) and Phil Knight, *Shoe Dog* (EPUB; 美国; 25 units).

**Readable, not ingested** (alternates): 黄仁宇《赫逊河畔谈中国历史》, 钱穆《中国历代政治得失》, *The Worlds I See*, *Pierre Curie*. 《胡适口述自传》 is readable but kept out of the pool (owner: no further 胡适 stories for now).

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

20 units tried (18 in the validation run, 2 by the simulated nightly top-up); **10 candidates; 10 skipped**. Each skip has a stated reason, e.g. "本章是盛世经济与社会背景的概论…没有结局". 《中国财政史十六讲》 yields least: 4 of its 5 units were theory chapters.

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
| `bk-jiaohun-u13-1` | 军机处在承德复审叫魂诸案：衙役蔡瑞的“捏陷”供认、验辫尖，最终释放和尚、石匠与乞丐 (1768) | 《叫魂》第八、九章 · TXT offset 136038+ (nightly top-up) |
| `bk-mackay-u37-1` | 巴黎高等法院复审十四名被判死刑的“女巫”，医生报告她们“更需要药物而非惩罚”，全部释放 (1589) | Mackay · EPUB spine 37 (nightly top-up) |

## 4. Two articles through the normal chain

Both went through the chain every article uses: pre-draft source-context review → Claude draft / review / English → final editor (audit, revise, verify) → post-draft source-context review → admission. The model was Claude Opus (`claude-opus-5-5`, Claude Code CLI 2.1.308) at every step, as the final-editor records report it. The records are in `samples/auto/<id>/final/`.

**苏州城下的一份降约 / A Surrender Pact Outside Suzhou** (`cand-auto-20261101-bk-lhzz-u1-1`, 梁启超《李鸿章传》第三、四章). **Admitted.**
- Final editor attempt 1 left open issues; attempt 2 was admissible with no open issues. Across the record: 24 issues (8 facts, 7 unsupported, 2 quotes, 1 attribution, 1 parity, all fixed; 5 notes), 32 edits.
- Post-draft context review: clean, 2 notes, no evidence additions.
- Reading time: about 8 minutes (zh) / 11 (en).

**叫魂 (`cand-auto-20261101-bk-jiaohun-u14-1`, 孔飞力《叫魂》第九章).** **Admitted** under the title 一张没有抓到人的警网 / A Net That Caught No One.
- The final editor's attempts left a few attribution issues open. They were closed with recorded local fixes, as the standing owner rule allows (small, evidence-backed wording and attribution fixes). Each fix was re-verified by the final editor, and every quote was checked against the evidence pack:
  1. `CTX-X1..3`: state 孔飞力's own inference about 吴绍诗 (that he regarded the case as a false rumour) instead of the draft's guess;
  2. `V2-V1`: the type of resistance is this article's reading, and 孔飞力's inference stays his. The verifier's quote of E5 had a one-character typo (还有 vs 再有). The operator supplied the verbatim quote with `--basis`, and `local_fix` checked it against the pack before accepting it;
  3. `V3-V1`: the verifier's own proposed split, so that 吴绍诗's report to 弘历 and 孔飞力's narration (no arrests in 江西) are no longer one sentence.
- Final record: 12 issues (attribution 2, context 3, causality 2, parity 1, unsupported 1, all fixed; 3 notes), 14 edits, none open.
- Post-draft context review: clean, with 1 note: 孔飞力's "当时已七十岁" may refer to 1767.
- Reading time: about 9 minutes (zh) / 11 (en).
- It was also rehearsed with `hip adopt` on the production copy: admitted, plan unchanged.

**Using an article finished here in production: `hip adopt`.** Production does not re-run the model. `hip adopt ID` reads the records from `samples/auto/ID/final/`, registers the episode (dedupe check) and runs the unchanged admission: the final-editor record and the context review must be bound to exactly this content and evidence, and the sources are re-hashed from production's own source cache. Any mismatch leaves the edition pending with the reasons.

**Rehearsed on a copy of production data** (scratch directory; production untouched):
1. `hip library ingest --book all` fetched 叫魂 and 晚清七十年 (blob verified) and rebuilt all 8 books and 233 units. The units and source-cache text came out byte-identical to the worktree's.
2. `hip adopt cand-auto-20261101-bk-lhzz-u1-1` → admitted.
3. The stored plan (胡适, 吴起, then the mix) was unchanged.
4. The picker then offered an untried book unit in every category (none from the ledger).

## 5. How the nightly job keeps supplying

**No new timer.** `hip-prepare` (10:00 Beijing) already runs `hip nightly`. When fewer than 2 unprocessed candidates are waiting, it proposes for the categories the mix needs most; `pick_entry` now offers book units first. Then it drafts (at most 2 articles per batch) and runs the final editor.

**Simulated on real data.** `hip nightly --max-articles 1` was run once in the worktree. The supply step needed 中国古代 and 世界. It tried one unit for each, got a candidate from each on the first try (《叫魂》 unit 13, Mackay unit 37), and logged both with `source_kind: book`. The bounds held: at most 3 units per category and 8 proposal calls per night (`project.json` → `supply`).

The worktree's copy of the data lacked production's old final-editor attempt records. So the simulation also re-edited Snow and Curie there, which production skips: all its pending items have used their 3 attempts, checked with `final_edit.attempts_used` on the production database. Those simulation outputs were moved out of `samples/`, and the tracked records are unchanged.

**Pool size.** 233 units in 8 books. At this run's yield of one candidate per two units, that is roughly 100 candidates before new books are needed. Adding a book:
1. add its library.json entry: repository, commit, path, metadata, categories;
2. run `hip library ingest --book ID` (or `--book all`).

## 6. Deployment (after merging; nothing else changes)

Before 10:00 Beijing (the next `hip-prepare` run):
1. Merge `feature/book-supply` into `main`. On the Pi: `cd ~/history-in-practice && git pull --ff-only`.
2. Run `bin/hip library ingest --book all`. It:
   - fetches the two files production does not have yet (叫魂, 晚清七十年) from their pinned commits, blob verified;
   - ingests the eight usable books into the production data directory;
   - prints each book's level and unit count (expected: 233 units).
3. Run `bin/hip adopt cand-auto-20261101-bk-lhzz-u1-1 cand-auto-20261101-bk-jiaohun-u14-1`. It should print `"adopted": true` for each. If it doesn't, the edition stays pending with its reasons, and the nightly drafts nothing for it.
4. Nothing else: timers, recipients, the send time and the stored plan are unchanged. Adopted articles join the inventory, and the mix places them after the planned issues. The next `hip-prepare` drafts the remaining book candidates; when fewer than 2 are waiting, it proposes from untried book units.

**Rollback:** revert the merge. Book candidates not yet drafted are then never drafted, and the picker uses the catalogue only. Adopted articles are ordinary inventory: `hip requeue ID` sends one back to the pending queue, as for any other article.

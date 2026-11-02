# 2026-11-01 evening: column direction, more books, reading layout

Same branch as the book supply (`feature/book-supply`, PR #4). The send time (22:08 Beijing), recipients, the stored plan and the no-resend mechanism are unchanged.

## 1. Column direction, in the prompts that actually run

The column is for **good stories, the people's situations and choices, and better judgment**. Scholarly completeness is not the measure of an article.

**One shared rule block** carries this: `prompts/reader_first_zh.md` and its English counterpart `reader_first_en.md`. Every stage that proposes, drafts, reviews, edits or verifies includes it:
- `propose_candidate`, `propose_book`, `style_zh` (draft), `review_zh`, `edit_zh_en`, `final_audit`, `final_revise`, `final_verify`, `context_review`;
- `translate_en_long` (English).

The calls record which prompt files they actually sent (`calls.jsonl` → `prompts`).

**Material and honesty**
- Popular history, biographies, memoirs, business stories, novels and fables are all usable material.
- Articles stay faithful to the material and say naturally what it is ("据《明朝那些事儿》的讲述"). They need not prove every event from primary sources.
- A novelised telling is never presented as established fact. The model never invents dialogue or thoughts and passes them off as the book's.

**Writing**
- Make clear who is who, how they are related, what each wants, why they act, and what came of it.
- Same-title people are kept apart.
- Important classical lines are explained in the narrative.
- No review process in the body (no repeated "作者推断"). Attribution goes into the sentence, and material notes go at the end.
- The takeaway is concrete and bounded, without success-manual morals or a fixed template.
- The mix stays about 4 Chinese and 3 other stories per 7. War is not the axis. Familiar people's unfamiliar episodes come first, and textbook stories are avoided.

**Review priorities**
- **fix/block** only for:
  - wrong relationships;
  - wrong key causes;
  - distorted quotations;
  - seriously misleading claims;
  - invented material;
  - a reader unable to follow who is who or the key turn.
- **note** (any category, never a reason to rewrite): minor wording, side dates and disputes that exist in the material itself.

**Old conflicting rules removed:**
- "把单一来源写成定论";
- "只有一个史源时说明这一点";
- dropping 【文学化】 excerpts mechanically;
- "事实类问题不能是 note";
- "有史料记录的具体决策".

**Local fixes**
- After a local fix, the verifier reads the whole article but is told which fields changed. It raises fix/block only there, or for anything that changes the main line.
- `hip local-fix --wide` re-checks everything, for a fix that touches the core judgment.

## 2. Books

**New sources (owner links), checked against what was already here**
- **yaoxingle/bo-guan-yue-qu, 12-历史与世界格局:** 79 files. Its HEAD (1b0d81a) is the commit the library already pins. Two are duplicates of books in use (叫魂 as a PDF, 三案始末).
- **HarborLibrary/History-General:** 41 files, the same blobs as the saved tree. They are mostly the world wars and the Cold War. The scanned PDFs need OCR and were not used.

No bulk download: one file per selected book, Git-blob verified.

**Taken in this round** (`level` moves from selected to usable; the file stays on the Pi):

| Book | Source | Units | Note |
|---|---|---|---|
| 当年明月《明朝那些事儿》 | chenggaw/mingchaonaxieshier, 160 Markdown chapters (each blob verified), joined in SUMMARY order | 159 | novelised: attributed in every article |
| 黄仁宇《万历十五年》 | bo-guan-yue-qu PDF (text layer) | 21 | |
| 茨威格《人类的群星闪耀时》 | bo-guan-yue-qu PDF (text layer) | 13 | literary portraits: say so |
| 鲍恩《费城风云》 | bo-guan-yue-qu PDF (text layer) | 16 | 美国 |
| 麦克纳马拉《回顾》 | History-General PDF (text layer) | 25 | 美国; decisions, not battles |

**Readable but kept out:** 《天下无局：〈战国策〉里的实用智慧》 is a success-manual retelling ("悄悄努力，然后惊艳众人"). Its author is not named in the file.

**The pool:** 13 usable books, 467 units. Units with no usable heading are now named by their opening words.

**Continuous intake** is `hip library ingest --book all [--max-new 3]`:
- resumable: the local manifest is the checkpoint;
- deduplicated: a book already in place is not fetched or parsed again;
- bounded: at most N new files per run, one at a time, with the existing per-file and total byte caps;
- one book's failure is recorded without stopping the others.

The nightly proposal budget is unchanged: at most 3 units per category and 8 proposal calls per night, inside the existing `hip-prepare` window.

## 3. Rights: the public repository is not a copy of a book

`config/books/library.json` records `rights` per book. Only 梁启超《李鸿章传》, Mackay and the 1923 *Pierre Curie* are public domain; the rest are treated as in copyright.

**Kept in Git:** code, the book list and metadata, original work, articles (with short quotations) and run records.

**Stays on the Pi:** book files, parsed text, and the evidence packs of book-sourced articles. `.gitignore` covers `samples/auto/cand-book-*` and `cand-auto-*-bk-*` evidence; the files are kept locally.

**Audit:** `validation/public_text_audit.py` measures verbatim book text in every tracked file, and `tests/test_public_repo.py` keeps it under the limits (1,500 characters per file, 400 per string).

**What it found:**
- The 胡适 evidence pack (about 18,300 characters of 《胡适口述自传》, current and rev1) is in public `main`.
- This branch's 叫魂 pack has about 5,900 characters.
- Both are removed from the tip. Git history still holds them: removing them from history needs a force push, which is the owner's decision.
- Context reviews and run records hold only short quotations.

**Readers are never linked to a book file in a code repository.** The published 胡适 page linked "source" to the raw PDF. That link is now shown as a plain citation, on the web and in email, and new articles no longer carry such URLs.

## 4. Reading layout (display only; no sent article is rewritten)

**Web** (`templates/history_index.html`):
- **Order:** column · date · category · minutes → title → dek → language tabs and text size (A− / A+, remembered) → body.
- **Text:**
  - Chinese body 18px on phones, 18.5px on desktop, line height 1.85, column 640–680px;
  - English column about 620–660px, line height 1.7, hyphenation;
  - title 28 / 34px, section headings 20 / 22px;
  - 20px side margins on phones.
- **Behaviour:**
  - switching language keeps the paragraph being read;
  - a folded contents list appears only for pieces with 4+ sections;
  - the example answer is folded;
  - 本篇依据 / 出处与不确定性 / 想再读一点 are in one folded "书目与补充说明" block, which `#notes` opens;
  - corrections stay visible above the body;
  - no edition id or revision for readers.

**Email** (`render.email_html` / `email_text`), from the next issue:
- **Order:** column · date → title → **[在网页阅读] [Read in English]** → dek → body.
- **Buttons:** 44px tall; they wrap on narrow screens and are tables for Outlook.
- **Text:** body 18px with line height 1.85; headings 20px; side padding about 20px on phones and 36px on wide screens.
- **Notes:** one short line plus a link, with no folding and no script.
- **Footer:** date, web and English links, feedback, pause.
- **Removed:** internal ids, revisions and review details.
- **Kept:** both languages in full.
- **Dark mode:** styles for clients that honour `prefers-color-scheme`.
- **Plain text:** the two links come right after the title.

## 5. The rule check: one new story through the normal chain

**《钥匙扔进阴沟之后》 / After the Key Went Down the Drain** (`cand-auto-20261101-bk-ming-u51-1`): **admitted** (worktree; production via `hip adopt`).
- **Episode:** 1457, 夺门之夜. 徐有贞 knows the plan has a hole (no key to the palace gates), moves anyway before the next morning's memorial, and throws the gate key into the drain.
- **Source:** proposed automatically from 《明朝那些事儿》 chapter 22 by the nightly picker's book path. The first unit tried gave a candidate.
- **Every call loaded the new rules:** `reader_first_zh` c456b6a296e7, `reader_first_en` d60a0a5e1df4 in the proposal, draft, review, English, final audit, revise and verify calls (`calls.jsonl` → `prompts`).
- **Model:** Claude Opus `claude-opus-5-5` via the Claude Code CLI at every step.
- **Reading time:** about 9 minutes (zh) / 13 (en).

**What the rules changed in the text**
- The material is named once, up front: "下面的故事依据当年明月《明朝那些事儿》的讲述。这本书写得像小说……凡涉及心思和评价，都按书里的说法转述". After that, the book's views are attributed in the sentence ("当年明月相信……", "书里说……").
- No "作者推断" labels.
- A short section introduces who is who: 朱祁镇 / his brother 朱祁钰 / 石亨 / 徐有贞.
- 「所请不允」 and 「事济否」/「必济」 are explained in the narrative.

**Review under the new priorities:** 25 issues, of which 17 were notes and 8 fixes (all closed), over 3 final-editor attempts. The post-draft context review was clean, with 3 notes recorded and not acted on, for example: the delay by 朱祁钰 used as a positive example in the reference answer fits the book less well.


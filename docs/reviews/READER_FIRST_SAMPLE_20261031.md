# Reader-first Chinese sample (2026-10-31, prompts/07)

## Selection (internal editorial judgment, not a factual claim about what readers know)

Compared only material already on the Pi (no new acquisition):

| Candidate | Source | Why not / why |
|---|---|---|
| 廉颇蔺相如 位次之争 (admitted) | 史记 | **Excluded by the owner**: textbook story (负荆请罪); a new angle does not make it new. |
| 井陉口前，那条没人听的计 (admitted) | 史记 | Leads into 背水一战, a familiar idiom; a war story. |
| 海瑞上疏 (evidence pack ready) | 明史·海瑞传 | 海瑞 and the memorial are widely retold (罢官, 备棺); a confrontation story rather than a less-known episode. |
| 吴起辞婚 (admitted) | 史记·吴起列传 | Strong runner-up: a familiar person, a less-told scheme, few actors. Kept as the fallback if the chosen story fails its checks. |
| 左宗棠/伊犁, 铁路议奏 (qsg412/437) | 清史稿 | Diplomacy and memorials, with many officials and foreign names, plus numbers; harder to get into. |
| 信陵君 夷门 (sj077, pending) | 史记 | 窃符救赵 is a textbook story. |
| **胡适：只剩诗这一处 → 《尝试集》 (chosen)** | 胡适口述自传 (唐德刚译注), text-layer PDF from the fork, pp. 86–96 + context additions | See below. |

Why 胡适:
- **Familiar person, less familiar episode.** Most readers know 胡适 and 白话文. Fewer know the concrete chain that led to it:
  - a farewell poem teased by friends;
  - a year of arguing;
  - a near-capsize on a lake in July 1916 and the old-style poem written about it;
  - the friends retreating until only "poetry" was left;
  - his choice to *test* it himself (《尝试集》) rather than argue on;
  - publishing under the deliberately mild "改良/刍议";
  - 陈独秀 then raising it as "文学革命".
- **Accessible setting.** The question is about the language the reader is reading right now.
- **Few essential actors:** 胡适, 梅光迪, 任鸿隽, then 陈独秀.
- **No statistics, no war.**
- **Something new to learn:** how an unwinnable argument was narrowed to one point and turned into a public experiment, and the trade-off between mild wording and someone else raising the banner.
- **Limits:** the single source is 胡适's own late oral memoir (abridged and back-translated), and his friends' words are reported by him. The article must say so briefly.

Process: the full episode and its ending (pp. 86–96, plus the context review's additions HS-E30…E36) were read before drafting. The article then goes through:
1. the MiMo draft;
2. the Claude final editor (with 3 bounded attempts);
3. the source-context review;
4. a recorded reader-first restructure request (`data/hushi_reader_issue.txt`), checked again from scratch.

No approval is carried over across a rewrite.

## Result (2026-10-31 15:41 CDT)

**Status:** admitted.
- Attempts used: 3, plus 2 owner-directed. The second extra attempt was allowed only because the context review had added evidence the editor hadn't seen (HS-E39).
- Then one **local fix**, authorized by the owner and *not* counted as an attempt:
  - Issue V2-V1, hook.1: the article said "按胡适的说法，难处在于…". In the source, this is 胡适 setting out *his friends'* objections in order (HS-E20, "我开始用的战术是把他们反对我的原因排个队").
  - Fixed in zh and en.
  - The translator's 〔〕 insertions ("为攻克这最后一个堡垒", "在中国诗词中") were deliberately *not* attributed to 胡适.
- After the fix:
  - a fresh full verify pass on the exact new text found no open issues;
  - the context review was clean;
  - approval record ed344b7aec47, content_sha256 ee6e7e10…;
  - `current_eligibility` re-verified: no problems.

The checks so far are model checks: the final editor, the deterministic checker and the context review. **No reader has approved this story yet.**

### Before (the first final-editor version) → after (reader-first revision)

| | Before | After |
|---|---|---|
| First sentence | Gives away the ending: "1916年七月底八月初…胡适给自己定了一条规矩：不再写旧诗词…叫《尝试集》" | Opens on the tension: "一群在美国读书的中国朋友，为中国文学该怎样改革争论了一年多。1916年7月，湖上一场几乎翻船的风雨…争论最后收缩到一个问题上：诗能不能用白话写。" |
| Opening background | The leaflet side story first, with 清华学生监督处, 钟文鳌, and 美东中国学生会文学股 | The main conflict first; the leaflet is compressed into the context section; those institution names are gone |
| Secondary names (zh body, mentions) | 钟文鳌 1, 赵元任 3, 陈衡哲 1, 钱玄同 1, 白璧德 2, 爱默生 1, 剑桥 1, 绮色佳 2, 唐德刚 9 | 钟文鳌, 陈衡哲, 钱玄同, 白璧德, 爱默生 and 剑桥 removed; 赵元任 1, 绮色佳 1, 唐德刚 6 |
| Main cast | 胡适, 梅光迪, 任鸿隽, 陈独秀 | Same four, each introduced with their role on first mention |
| Limits section | 3 paragraphs, 584 chars, including the 元明之辨 note and a counterfactual disclaimer | 3 paragraphs, 330 chars |
| Length / estimate | 4,788 zh chars, 3,526 en words; ≈15 / 18 min | 4,840 zh chars, 3,549 en words; ≈15 / 18 min |

**Not achieved:** the ~10-minute target. The revision moved and replaced material rather than cutting it. The reading estimates use 320 zh chars/min and 200 en words/min, and count the body plus the question and the example.

### Test-site preview

- **Where:** branch `hip-test-20261030` of the website_test repo (preview only; `main` is unchanged).
- **What's on it:**
  - a homepage card "没事儿多读书", plus a short "读书" nav link;
  - the story directory with 胡适 first, marked 推荐 · 样稿;
  - Snow last, with a dated 待修订 notice. The sent revision 1 is byte-identical (sha256 809c603d…).
- **Live check:**
  - the served JSON hash matches and was recomputed;
  - phone viewport 390 px (headless Firefox, iPhone user agent): home → card → list → zh/en story, with no horizontal overflow and no load errors.
- **Known issue (pre-existing):** the homepage's top nav is too crowded on phones ("Contact" was already cut off). The card is the working entry.

## Revision 2: the reader-first abridgment (owner request, 2026-10-31 evening)

**Status: pending_review. Not approved.** Revision 1 is archived intact (`samples/auto/cand-book-20261031-hushi-baihua/revisions/rev1/`). On the test site, revision 1 now carries a dated notice and is no longer recommended.

| | rev 1 (approved 15:41) | rev 2 (current text) |
|---|---|---|
| Chinese body + question + example | 4,840 chars, ≈15 min | **3,019 chars, ≈9 min** (target 3,000–3,200) |
| English | 3,549 words, ≈18 min | **2,166 words, ≈11 min** (target 1,800–2,000: over by ~170) |
| Sections | hook 2 · context 3 · story 10 · analysis 4 · today 2 · limits 3 | hook 2 · context 2 · story 9 · analysis 3 · limits 1 (the "today" section is gone) |

**What was cut or changed:**
- **Opening:** now starts with the letter from Ithaca and the near-capsize, and states that 胡适 was not in the boat (HS-E38: he received a letter from Ithaca). It ends on the question "能不能用白话写诗？".
- **Leaflet side story:** cut to a few lines.
- **Literary-tools history:** two sentences.
- **Nine diary points:** one paragraph, which sets up the timing.
- **1920 education order:** kept as one closing line, with 胡适's own dissatisfaction.
- **The 逼上梁山 dictionary gloss:** removed from the Chinese.
- **Three modern scenes → one:** the "today" section is gone; one scene is merged into the question. The checker now allows this (owner decision; fact checks unchanged).
- **Limits:** cut to one short line in the body; the rest is in the expandable end note.

**How it was checked:**
1. One owner-authorized whole-article attempt (attempt-6). The final editor raised 13 issues on my draft, for example: the dek said "stopped arguing"; a suggestion of collusion between 胡适 and 陈独秀 had no basis; "about four years" was overstated; May Fourth's "干扰" was missing. All were revised.
2. Local fix of story.4 chronology ("最后" → "特别").
3. Context review: needs work. The end note was too absolute, 胡适's own view of the new poetry was missing, and HS-E40 had to be added.
4. **Incident:** the local-fix command then started whole-article attempts 7 and 8 that nobody requested. I stopped attempt 8 mid-run; fixed in bcdd788 with a test. Record: `revisions/incident_20261031_unrequested_attempts.json`.
5. Local fix of attempt 7's text: story.3 attribution, plus your instruction to drop the Chinese idiom gloss, which attempt 7 had re-added. The final editor's fresh verification was clean.
6. **Context review: needs work. Stopped here, per the owner rule.**
   - **(a) Wrong chapter citation:** the episode is in chapter 7 《文学革命的结胎时期》; only the outcome is in chapter 8. Verified at source offsets 101,760 / 118,184. Revision 1 had the same error.
   - **(b) HS-E41:** 胡适 himself ties the experiment, and the name 《尝试集》, to Dewey's experimentalism. The article presents that framing as the author's inference.

**Next step (needs the owner):** one recorded fix: the chapter citation in `sources` and the end note, and re-attributing analysis.1's "experiment" framing to 胡适's own explanation (HS-E41). After that, one context review.

### Revision 2 completed (owner go-ahead, 2026-10-31 night): admitted

**Status: admitted** (final-editor record `9f9608911724`, content `9dc2863a`, clean context review bound to that text). On the test site it is a recommended sample; revision 1 stays archived with its records.

| | rev 1 | rev 2 as admitted |
|---|---|---|
| Chinese | 4,840 chars, ≈15 min | **3,081 chars, ≈10 min** |
| English | 3,549 words, ≈18 min | **2,216 words, ≈11 min** (accepted by the owner; no rewrite to reach 2,000) |

**What the fix changed (only these sentences and their links):**
- **Chapters:** the events are cited to chapter 7 《文学革命的结胎时期》, the outcome to chapter 8 《从文学革命到文艺复兴》. This is in the end note, the materials note, the source citation and the read-more title. 唐德刚's note on the abridged, hand-revised and back-translated English draft is limited to chapter 7.
- **Dewey:** analysis.0 now reports, as 胡适's own statement, that he named 《尝试集》 under the influence of the American philosopher Dewey's experimentalism, with poetry as the part left to test (HS-E41). analysis.1 ("作者推断") now holds only the article's own additions: naming the book in advance as a burden of proof, the written-down retreat, and the low-key publication.

**Root cause of the wrong chapter (in rev 1 too):** the evidence pack's *source title* said "第八章" for every excerpt, so the drafter and the final editor both saw chapter 8. The first verify pass after the fix therefore flagged the correct citation as unsupported (V4-V1, V4-V2). The pack metadata was corrected from the source's chapter headings:
- The new chapter-heading excerpts are cut verbatim from the source: HS-E42 (chapter 7 heading) and HS-E43 (end of the chapter 7 notes plus the chapter 8 heading).
- Normalised offsets: chapter 7 starts at 99,581 and chapter 8 at 115,735.
- Each excerpt label now carries its chapter: 38 excerpts are in chapter 7, and HS-E30, E37 and E40 are in chapter 8.
- No excerpt's quote, offset or id changed.

The two issues were then rejected, with quotes taken from the corrected pack. A fresh verify had no open issues, the context review was clean, and the text was admitted. Records:
- `data/local_fixes/hushi_rev2_*`
- `localfix-attempt-7-4` and `localfix-attempt-7-5`
- `context-20261031T195747_review.json`

**One note-level point left for a later revision:** the context review notes that "陈独秀随即写了《文学革命论》" is slightly quicker than the source ("在《新青年》的后一期"). A local fix cannot touch admitted text, and this was not worth another demotion.

## 吴起辞婚: reader-feedback revision (owner, 2026-10-31 night)

**The reader's feedback:**
- The body kept interrupting itself with "作者解释 / 原文没写，本文不补写".
- Key classical lines and the relationships between people were not explained.

**The owner's request:** a scoped readability revision. Its main line is the marriage test; the 鲁国 and 楚国 parts are kept only as background.

**Drafting rev 2 (by the operator, from the evidence pack only):**
- **People and the test:**
  - 公叔 is introduced as 魏相 and the princess as his wife.
  - The home scene and 武侯's marriage offer are told as the two steps of one test.
- **Classical lines and judgments:**
  - 「猜忍」 is translated as 多疑狠厉 and attributed to the accuser.
  - 田文's answer is explained: a young ruler and an uneasy state, and personal merit against the chief minister's present duty.
  - 李克's 「贪而好色」 and the servant's 「节廉而自喜名」 are each labelled as that person's judgment.
- **Removed from the body:**
  - the process notes (原文没写/本文不补写, 此处录其二, （作者解释）);
  - the "最刺眼的一笔" verdict;
  - the boat speech;
  - the "today" section, so the modern scene now lives only in the question.
- **Background:** the 鲁国 and 楚国 parts are each cut to one paragraph.

**Checking:**
- One revision attempt (attempt-4; the three earlier attempts are kept).
- The final editor fixed 15 precision points, for example: "无人能比" → what 田文 admitted; "除掉" → "赶走" (害/易去); 置相 is appointing, not creating the office; the history's own causal 「故」 is restored.
- Then two local fixes under the standing rule:
  1. the English "privileges" (not in 廢公族疏遠者);
  2. naming 武侯 as the ruler, separating the two princesses, and marking the plan as a plan in Chinese as well as English.
- Length: zh 2,544 → about 2,200 chars (≈7 min); en 2,438 → about 1,750 words (≈9 min).

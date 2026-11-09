# 原文精选 sources: modern vernacular only (2026-11-09)

**Owner's correction (2026-11-08).** 原文精选 means reading words that an author or a human translator wrote, with their narrative and language kept and no LLM rewriting. A Chinese body must be modern vernacular:
- **Allowed:** modern Chinese writing (history, biography, memoir, popular history, social and economic stories); human vernacular translations of old texts; modern authors' explanations and commentary. Foreign works get a labelled Chinese AI translation.
- **Not allowed as a Chinese body:** classical or semi-classical texts, or editions hard for a modern reader. Converting traditional characters to simplified does not make a text vernacular, and publication date or title is no substitute for reading it.

## How the rule is enforced

**Reading decides; the score screens** (owner's follow-up, 2026-11-09). The register score (`excerpt.register`, `VERNACULAR_MIN = 30`) counts modern function words (的了们这那么吗呢着) per 1,000 Chinese characters. It catches obvious classical text but does not measure readability, so it never decides alone:

| Text | Modern | Classical | Result |
|---|---|---|---|
| 鲁迅《范爱农》《琐记》, 刘鹗《老残游记》, 孔飞力《叫魂》 | 83–92 | | vernacular |
| 唐德刚《晚清七十年》 | 45 | | vernacular |
| 梁启超《李鸿章传》 (1901) | 0.6 | 86 | classical |
| 《浮生六记》 | 0.5 | 70 | classical |
| 《史记》 | 0 | 117 | classical |

- **Every Chinese-original issue is read through.** The review reads the whole body and records a verdict (`readable` or `hard`) with its reason. `hard` blocks the issue at any score.
- **A score under 30 is a flag, not a refusal.** Such a passage can be used only with a recorded read-through that finds it readable and says why. Without that record, admission, eligibility and the send gate refuse it.
- **Editions read and confirmed classical stay out:** 《史记》, 《浮生六记》 and 《李鸿章传》 (library `register: classical`). The supply skips them and the send gate refuses them, whatever a review says. They can come back with a human vernacular translation.
- **Library ingest** records each Chinese book's score as a hint (`register_hint`). Only a reader's judgment sets `register`.
- **Prompts:** selection and review read first and ask whether an ordinary modern reader can follow the people, events and connections without leaning on notes. A classical or note-dependent body is skipped, or a must-fix review issue. The model never turns classical text into vernacular as a stand-in.

## Books: reading fit and publication status, recorded separately

| Book | Author | Edition | Reading fit | Publishable at length |
|---|---|---|---|---|
| 《回忆鲁迅先生》 (1939) | 萧红 | zh.wikisource rev 2766766 | memoir, vivid vernacular; modern 102 | yes: author d. 1942 |
| 《多余的话》 (1935) | 瞿秋白 | rev 374021 | personal reckoning, vernacular; 95 | yes: d. 1935 |
| 《我在北京大学的经历》 (1934) | 蔡元培 | rev 2429668 | memoir, plain vernacular; 50 | yes: d. 1940 |
| Memoir essays: 二十四孝图; 关于太炎先生二三事; 因太炎先生而想起的二三事; 忆韦素园君; 忆刘半农君 | 鲁迅 | Wikisource revisions per page | 81 | yes: d. 1936 |
| 《范爱农》, 《琐记》 | 鲁迅 | as before | vernacular | yes |
| 《老残游记》 | 刘鹗 | as before | late-Qing vernacular novel, readable; 83 | yes |
| English originals with an AI Chinese translation: Yung Wing; Franklin, *Autobiography*; Darwin, *Autobiography*; Douglass, *Narrative*; *Up from Slavery*; Shackleton, *South*; *Pierre Curie* (1923) | | | | yes |
| *Autobiography of Andrew Carnegie* (1920): business, economics | Andrew Carnegie | Gutenberg #17976 | memoir: telegraph boy to steel; how he ran firms, chose people, gave money away | yes: d. 1919 |
| *My Life and Work* (1922): business, technology | Henry Ford, with Samuel Crowther | Gutenberg #7213 | first-person account of mass production and the $5 day | yes: published 1922 in the US; both d. 1947 |
| *Personal Memoirs of U. S. Grant* (1885–86): political and military decisions | Ulysses S. Grant | Gutenberg #4367 | plain, famous memoir: judgments in the Civil War, Appomattox | yes: d. 1885 |
| *Extraordinary Popular Delusions*, vol. I (1852 ed.): economics and finance | Charles Mackay | Gutenberg #24518, plain text | the Mississippi Scheme, the South Sea Bubble, tulip mania. Its EPUB is not used: chapter titles there are picture captions | yes: d. 1889 |
| *The Chemical History of a Candle* (1861): science | Michael Faraday | Gutenberg #14474 | Christmas lectures for young people, built on experiments | yes: d. 1867 |
| 《李鸿章传》, 《浮生六记》, 《史记》 | | Wikisource / EPUB | classical: out of 原文精选 | yes, but not used as a body |
| 《叫魂》, 《晚清七十年》, 《万历十五年》, 《明朝那些事儿》, 《三案始末》, etc. | | owner's Git catalogues | vernacular, good reading | no (in copyright): topics and internal reading only |

**The owner's catalogues, re-checked:**
- **Git: no modern Chinese edition confirmed suitable for long public excerpts has been found this round.** That is not a finding that every file is in copyright. The per-file record is `config/book_candidates/catalog_check_20261109.tsv`, with 1,813 book files in 14 repositories at their pinned commits. Each file's status is one of:

  | Status | Files | Meaning |
  |---|---|---|
  | in the library | 15 | ingested and checked; level and rights recorded |
  | public domain but classical | 130 | 《史记》 chapters (gh73962/shiji_md) |
  | to check: may hold public-domain documents | 131 | the 1840–1949 document anthology (treaties, declarations, memorials, speeches); author, date and register differ piece by piece |
  | in copyright (contemporary) | 159 | 《明朝那些事儿》 chapters: readable vernacular; topics and internal reading only |
  | not checked one by one | 1,378 | only their file names were searched for public-domain-era authors (鲁迅, 萧红, 郁达夫, 瞿秋白, 蔡元培, 邹韬奋, 徐志摩, 许地山, 刘半农, 李大钊, 梁启超, 林纾, 王国维); none matched. Author dates, edition and translator are not yet checked |

  Update a row's status and note as each file is checked. The earlier figure of 1,962 counted every file in those repositories, not only books.
- **Google Drive:** only the 63 top-level folder names are listed (传记, 纪实, 中国, 经典古籍, …). The contents were never enumerated because the download path is not connected, so nothing there is usable yet.

**Where more publishable modern Chinese comes from:**
- authors who died by 1945, so the work is public domain in China and was not restored in the US: 鲁迅, 萧红, 瞿秋白, 蔡元培, 郁达夫, 邹韬奋, 徐志摩, 许地山, 刘半农, 李大钊;
- texts on Wikisource or in other public-domain editions;
- human vernacular translations that are themselves public domain.

## Variety (owner, 2026-11-09)

The plan for 11-09 to 11-15 has six Chinese pieces out of seven, several around 鲁迅 and late-Qing literature. That is fine for a transition. Later issues should bring in economics, business, science, political decisions and a wider range of people, in the column's aim of 读书明事理.

- **Nightly supply order:**
  1. Each candidate book is scored by its least-covered theme across the latest 14 原文精选 (sent, scheduled or ready).
  2. Economics and finance, business, science and technology, and politics and governance get a half step forward; so do Chinese originals.
  3. An author who appeared lately gets a half step back per recent appearance.
  4. The order is recomputed after every run.
- **Plan:** a 原文精选 carries its book's themes, so consecutive days vary the theme as well as the book and author.
- **Gutenberg plain text:** picture markers and footnote blocks are not running text. They are left out of the passage without a 〔中略〕 mark, and _italics_ are shown as italics. The author's words are never changed, and the source checks are unchanged.

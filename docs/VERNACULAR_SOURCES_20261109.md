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

## 《史记》 and 《资治通鉴》 in modern Chinese (owner, 2026-11-09)

The owner asked for human vernacular translations and modern explanations of 《史记》 (such as 韩兆琦's annotated translation or 王立群读《史记》), and for the 柏杨 《资治通鉴》 in the catalogue. The 130 《史记》 files are the 130 chapters of one classical edition (gh73962/shiji_md); they are not a check of other editions. The topic stays open even though only the classical text is connected now.

| Edition | In the catalogues? | Readable modern Chinese? | Publishable at length? |
|---|---|---|---|
| 韩兆琦, 《史记》 annotated translation | no | not read (no file) | no: a contemporary translation, in copyright |
| 王立群读《史记》 | no | not read (no file) | no: the author was born in 1945; in copyright |
| Other complete vernacular 《史记》 (杨燕起 et al., 《白话史记》; the Taiwan 《白话史记》) | no | not read | no: contemporary, in copyright |
| A public-domain human vernacular translation of 《史记》 | none found | | |
| HarborLibrary/Chinese-History 「资治通鉴 (柏杨白话版)」 EPUB and MOBI | yes | the translation is readable (58.5) | no: a contemporary translation, in copyright. **Translator not verified.** Classical and vernacular paragraphs alternate. The file has no copyright page and no translator credit (OPF publisher “babyshan”, source “Freesource”), and “柏杨版” is only in the title. It has not yet been compared with 柏杨's own text, so it cannot be called 柏杨's translation or not. The list's 《柏杨白话版资治通鉴（全72册）》 is to be downloaded and compared paragraph by paragraph. Internal reference only |
| 柏杨's own 《白话资治通鉴》 | no | | no: 柏杨 d. 2008, in copyright until 2058 |
| 吕思勉《白话本国史》 (1923), miraclestar43/bo-guan-yue-qu | yes | 1920s vernacular with many classical quotations and philological asides. The narrative parts read well (the 秦始皇 section scores 61); the philological parts are hard, so excerpts take narrative only. Years are counted before the Republic (前2124年 = 213 BC) and need a note | **yes**: 吕思勉 d. 1957, and a 1923 publication is also public domain in the US. This file is a 2023 calibre conversion with no source edition named. Its contents page is empty and most chapter headings are lost, so it cannot be ingested as is. A copy with its headings is needed (not on Wikisource) |
| 朱自清《经典常谈·史记汉书第九》 (1942) | Wikisource rev 2565718 | yes: vivid; it retells 司马迁's life, the 李陵 affair and how the two histories differ (66.7) | public domain in China (d. 1948). In the US, a 1942 work was probably restored until 2037. Under the current rule (author d. by 1945, or published before 1931) not yet: **owner's decision** |
| 蒋廷黻《中国近代史大纲》 (1938), HarborLibrary/Chinese-History PDF; Wikisource rev 2636855 | yes | yes: plain vernacular (PDF 56, Wikisource 70) | public domain in mainland China and Taiwan (d. 1965). The US is probably restored until 2033: same owner decision |
| 吕思勉《吕著中国通史》 (1940) | Wikisource | not read this round | public domain in China. The US is probably restored until 2035: same decision |
| 张荫麟《中国史纲》 (1941; covers up to the Eastern Han) | no text source found | not read | yes: d. 1942, public domain in China and not restored in the US. A text source is needed |
| 梁启超《要籍解题及其读法》, including the 《史记》 essay (1925) | no text source found | not read | yes: d. 1929, published 1925 |

The record rows for the catalogue files are updated in `config/book_candidates/catalog_check_20261109.tsv`. Google Drive's 「经典古籍」 folder is still not enumerated.

## The human 《史记》 translation, the inbox and the download test (owner, 2026-11-09)

**Book.** The owner downloaded 《史记（精注全译）》（全12册） from a 城通网盘 page in jbiaojerry/ebook-treasure-chest `md/历史.md`; `~/Downloads/史记-原文-翻译.epub` is the only file there and stays where it is.
- **Edition, from the cover image and the OPF:** [西汉]司马迁 著，石磊 主编，中国文史出版社, twelve volumes; EPUB metadata date 2021-09-13, Kindle ASIN B09G5TY32C. The file has no copyright page, so the ISBN, the print year and the translator of each chapter are recorded as not verified.
- **Layout:** each chapter has an editor's preface, then 【原文】+【注释】 blocks, then one 【译文】 block (`div.yw`) holding the whole chapter's human translation.
- **Reading view** (library `view`, `books.load`): only the 【译文】 paragraphs and the chapter title are kept; a spine file that opens on a label continues its chapter. The result is 130 chapters and 4,962 translation paragraphs, with no original text, note numbers or labels. 331 rare characters are pictures in the book and show as □; a passage containing one is refused until the character is read from the picture. The 12 paragraphs at the end of 《天官书》 that explain corrupt text sit under 【注释】 and are not kept.
- **Library:** `BK-SHIJI-SL`, rights `in_copyright` (a 2021 translation), so the nightly supply never picks it. The credit line names both 司马迁 (原著) and the translation (石磊 主编，各篇译者书中未署名), in email and on the web.

**Local sample:** 《袁盎晁错列传》, the whole chapter in the book's translation: 22 paragraphs, about 19 minutes in Chinese, 14 notes, two questions and a folded reference angle; checks pass.
- Two small issues were fixed locally and recorded: an English note label, and a reflection fix that had pasted “同 Q3 修改后的 angle.zh 全文” in as text. The code now refuses such cross-references.
- The sample is not admitted, scheduled or sent. Public use (web or email) needs permission and is a separate question.

**Inbox** (`hip books inbox`, `hip books import-local --book ID --path FILE`): lists `~/Downloads`; unpacks .zip, .7z and .rar into `data/books/inbox/` with name and size checks, keeping the original; reads what each file says about itself; and marks files already acquired (same bytes) or with a possible duplicate title. Importing copies a file into the book store under the same caps. The only manual step is the download.

**Download test (城通网盘):**
- The page loads with curl only as a shell; the content comes from scripts.
- Headless Chromium hangs on the page; its DevTools endpoint stopped answering.
- Headless Firefox shows only the loading skeleton.
- No attempt was made to get round the site's checks.
- Downloads from this site are therefore done by hand in a normal browser; everything after the file reaches `~/Downloads` is automated.

**Book list:** 1,748 entries parsed; 6 are already in the library. Ten candidates, and every book's five statuses (acquired / edition verified / text extractable / reading fit / public long excerpt), are in `config/book_candidates/intake_status_20261109.tsv`.

## Variety (owner, 2026-11-09)

The plan for 11-09 to 11-15 has six Chinese pieces out of seven, several around 鲁迅 and late-Qing literature. That is fine for a transition. Later issues should bring in economics, business, science, political decisions and a wider range of people, in the column's aim of 读书明事理.

- **Nightly supply order:**
  1. Each candidate book is scored by its least-covered theme across the latest 14 原文精选 (sent, scheduled or ready).
  2. Economics and finance, business, science and technology, and politics and governance get a half step forward; so do Chinese originals.
  3. An author who appeared lately gets a half step back per recent appearance.
  4. The order is recomputed after every run.
- **Plan:** a 原文精选 carries its book's themes, so consecutive days vary the theme as well as the book and author.
- **Gutenberg plain text:** picture markers and footnote blocks are not running text. They are left out of the passage without a 〔中略〕 mark, and _italics_ are shown as italics. The author's words are never changed, and the source checks are unchanged.

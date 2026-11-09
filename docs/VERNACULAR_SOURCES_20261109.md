# 原文精选 sources: modern vernacular only (2026-11-09)

**Owner's correction (2026-11-08).** 原文精选 means reading words that an author or a human translator wrote, with their narrative and language kept and no LLM rewriting. A Chinese body must be modern vernacular:
- **Allowed:** modern Chinese writing (history, biography, memoir, popular history, social and economic stories); human vernacular translations of old texts; modern authors' explanations and commentary. Foreign works get a labelled Chinese AI translation.
- **Not allowed as a Chinese body:** classical or semi-classical texts, or editions hard for a modern reader. Converting traditional characters to simplified does not make a text vernacular, and publication date or title is no substitute for reading it.

## How the rule is enforced

**The register gate** (`excerpt.register`, `VERNACULAR_MIN = 30`) measures modern function words (的了们这那么吗呢着) per 1,000 Chinese characters:

| Text | Modern | Classical | Result |
|---|---|---|---|
| 鲁迅《范爱农》《琐记》, 刘鹗《老残游记》, 孔飞力《叫魂》 | 83–92 | | vernacular |
| 唐德刚《晚清七十年》 | 45 | | vernacular |
| 梁启超《李鸿章传》 (1901) | 0.6 | 86 | classical |
| 《浮生六记》 | 0.5 | 70 | classical |
| 《史记》 | 0 | 117 | classical |

- **Excerpts:** a Chinese-original passage under 30 fails the mechanical checks. That blocks admission, eligibility and the send gate, so an old classical piece cannot be picked again.
- **Library:** ingest records each Chinese book's register. Classical books leave 原文精选 selection, while staying available for choosing topics and internal reading. They can come back with a human vernacular translation.
- **Prompts:** selection and review must read first and ask whether an ordinary modern reader can follow the people, events and connections without leaning on notes. A classical or note-dependent body is skipped, or a must-fix review issue. The model never turns classical text into vernacular as a stand-in.

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
| 《李鸿章传》, 《浮生六记》, 《史记》 | | Wikisource / EPUB | classical: out of 原文精选 | yes, but not used as a body |
| 《叫魂》, 《晚清七十年》, 《万历十五年》, 《明朝那些事儿》, 《三案始末》, etc. | | owner's Git catalogues | vernacular, good reading | no (in copyright): topics and internal reading only |

**The owner's catalogues, re-checked:**
- **Git:** 1,962 book files in HarborLibrary ×9, bo-guan-yue-qu and english_ebooks. None is by a modern Chinese author whose works are public domain (died by 1945). They are contemporary, in-copyright books: good for choosing topics, not for long public excerpts.
- **Google Drive:** only the 63 top-level folder names are listed (传记, 纪实, 中国, 经典古籍, …). The contents were never enumerated because the download path is not connected, so nothing there is usable yet.

**Where more publishable modern Chinese comes from:**
- authors who died by 1945, so the work is public domain in China and was not restored in the US: 鲁迅, 萧红, 瞿秋白, 蔡元培, 郁达夫, 邹韬奋, 徐志摩, 许地山, 刘半农, 李大钊;
- texts on Wikisource or in other public-domain editions;
- human vernacular translations that are themselves public domain.

The nightly supply takes Chinese originals first, from these books.

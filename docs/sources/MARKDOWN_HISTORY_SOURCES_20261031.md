# Markdown history/biography sources — checked 2026-10-31

These are GitHub sources inspected through repository metadata, trees/directories and representative actual file contents. A file listing and a spot check do not prove an entire book's completeness or historical accuracy. Preserve source edition/provenance and distinguish original text, annotations, modern interpretation and excerpts.

| Repository | Verified form / location | Use and limitation |
|---|---|---|
| https://github.com/gh73962/shiji_md | main; resource/ contains chapter-length Markdown text; 131 MD files across the repo including README; sampled 张仪列传 contains continuous historical narrative | Strong practical starting point for classical biographies. Verify edition/variants and chapter completeness before using a passage. Do not equate a repository licence with a licence for every annotation/edition. |
| https://github.com/gosaintmrc/zztj | main; 295 MD files including README; volumes arranged under dynasty directories; sampled A-周纪/1-資治通鑑卷第一卷-周纪一.md | Chronological historical material with dense inline HTML/font annotation and historical comments. Preserve original/annotation boundaries while removing markup. Count files separately from complete verified volumes. |
| https://github.com/baojie/shiji-kb | main; chapter_md/ contains numbered tagged chapter MD; sampled 065_孙子吴起列传.tagged.md | Entity/paragraph markup can aid event discovery. It needs a markup-aware adapter; generated entity labels, dates, wiki pages and analysis are not another independent historical witness. Its README describes AI knowledge processing and CC BY-NC-SA 4.0; inspect actual applicable licences before reusing its authored material. |
| https://github.com/biechuyangwang/jingdian | main; actual Markdown files under 史记/, 资治通鉴/, 战国策/, 世说新语/ etc.; sampled 管宁割席 has original, translation and interpretation | Convenient comparative reading / event leads. The README's completion claims have not been independently checked chapter by chapter. Keep commentary and modern applications separate from documentary text; independently verify interpretations. |
| https://github.com/sdlyyxy/Chinese-Modern-Contemporary-History-Anthology | master; dated event directories and actual historical-document MD, e.g. 1840-1949/戊戌变法/上清帝第二书.md | Useful for modern-China evidence/context, not a continuous general history or biography collection. Some texts explicitly say excerpt. Verify attribution, edition and event context. |
| https://github.com/chenggaw/mingchaonaxieshier | main; chaptered Markdown under src/, reading order in src/SUMMARY.md (already inspected in task 06) | Popular modern narrative; suitable for finding engaging episodes, with attribution and original historical cross-checks. Verify the selected volume/edition and completeness. |
| https://github.com/able8/weread-hot-booklists | main; books/人物传记/ includes 史蒂夫·乔布斯传.md, 富兰克林自传.md, 富兰克林传.md, 滚雪球… etc. | CAUTION: sampled Jobs and Franklin files are discontinuous popular highlights/notes (c: counters), NOT complete books. Use only as title/episode discovery; do not admit them as complete-source evidence. |
| https://github.com/OpenXinsheng/tianya | main; long MD files actually listed; mixes history/finance discussions, personal accounts and fiction | Optional low-priority discovery. Genre, authorship and assertions need checking; an anonymous post or a book-title-labelled post is not verified book text or historical evidence. |

## Selection for the current project

- First trial: gh73962/shiji_md for classical biography and the modern-history document anthology for modern-China contextual sources.
- Then zztj for chronological context and the existing EPUB books for modern/world biographies. Markdown is convenient, not a reason to prefer an incomplete text over a complete EPUB.
- Do not claim that this search found a verified full-text Markdown modern-biography library. The seemingly promising Jobs/Franklin hits inspected here were highlights. Record that negative result so the acquisition stage does not repeat the mistake.
- Task 06's HarborLibrary entries remain useful; markdown-source discovery should not restart a full acquisition project while the repair chain is running.

## Intake requirements

1. Remote metadata first, default branch resolved from GitHub, then a few selected real files.
2. Detect and record complete chapter vs excerpt vs reading notes vs authored commentary vs generated annotation. Reject an unverified completeness claim rather than promoting it based on .md extension.
3. Resolve reading order from a verified manifest/table of contents; do not sort Chinese numbered chapters lexicographically.
4. Keep source path/commit/hash and heading/paragraph/normalized offsets. Store no invented print page number.
5. Parse markdown/HTML/annotation as untrusted text only. Do not run repo tools, skills, scripts or build configs. Strip presentation markup while preserving source-vs-commentary boundaries.
6. Check the selected episode's lead-in AND conclusion, then build evidence and verified background; retain the context-review gate.
7. Private full texts, original bilingual public writing, appropriate attribution/quotations. Keep topic breadth and existing small acquisition/resource bounds.
8. Report actual parser/source/article results separately. No extra email, timer, production deploy or bulk clone is authorized by this discovery list.

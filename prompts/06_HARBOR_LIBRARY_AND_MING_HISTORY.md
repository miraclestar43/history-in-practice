# HarborLibrary and chaptered Ming-history sources

Owner supplement, 2026-10-31 (America/Los_Angeles). This supplements prompts/05_ADDITIONAL_BOOK_SOURCES.md and the active test/review work; it does not replace them. Keep topic breadth, draft PR, no production timers or official launch. The owner has already handed mail setup to the active Claude; inspect current runtime/send state, not stale claims of missing credentials. Reuse the existing test identity and never resend an accepted/unknown recipient.

## 1. Inspected sources

All ten user-supplied public repositories were inspected through GitHub metadata and complete recursive Git trees. This inspection verified listed Git objects, names, sizes, extensions and default branches, NOT book-body accuracy, completeness, successful binary download, parsing or reuse rights. No full book was downloaded during this review.

| Repository | Default branch | Blob entries | Extensions/counts |
|---|---|---:|---|
| chenggaw/mingchaonaxieshier | main | 163 | gitattributes 1, gitignore 1, toml 1, md 160 |
| HarborLibrary/Chinese-History | master | 220 | mobi 23, pdf 137, zip 8, chm 12, epub 23, txt 15, docx 1, rar 1 |
| HarborLibrary/Europe-History | master | 54 | pdf 43, epub 3, mobi 5, txt 2, chm 1 |
| HarborLibrary/History-General | master | 41 | txt 3, epub 6, pdf 22, mobi 4, chm 4, zip 2 |
| HarborLibrary/Social-Sciences | master | 33 | epub 8, mobi 7, pdf 14, txt 4 |
| HarborLibrary/Military-Science | master | 12 | pdf 12 |
| HarborLibrary/America-History | master | 11 | pdf 10, txt 1 |
| HarborLibrary/Asia-History | master | 19 | epub 2, pdf 15, mobi 1, zip 1 |
| HarborLibrary/Commerce | master | 91 | md 1, pdf 56, epub 12, mobi 11, txt 9, chm 1, azw3 1 |
| HarborLibrary/Political-Science | master | 425 | pdf 257, epub 63, txt 26, mobi 52, zip 13, chm 7, html 1, azw3 3, djvu 1, doc 2 |

For the nine HarborLibrary repositories combined:
- 906 blob entries, 900 distinct Git blob hashes, 4,705,833,413 bytes when counting each path once.
- Those are files, NOT 906 unique books. Same-book formats/translations/editions and duplicate files must be resolved.
- The recursive tree responses were not truncated.
- No repository licence was reported by GitHub metadata. Do not infer a book licence from repository visibility or from a repository-code licence.
- These are direct file listings, rather than only an index of external download pages. A selected file still needs a successful binary acquisition/integrity check.
- America-History means the Americas, not automatically the project's US slot. Classify by the actual event.
- Repository topic is a discovery tag, not evidence of genre or factual reliability. Political-Science includes fiction such as Orwell; do not mistake that for documentary evidence.

Inspected TREE hashes (tree identities, not asserted commit SHAs):
```
chenggaw/mingchaonaxieshier: 2ea18231209edbecb53ef29e7fcd48154eb23334
HarborLibrary/Chinese-History: c2851c6b90844fa4e9231514a404ad4fcc847f09
HarborLibrary/Europe-History: 03d5ccd15449fbed491003bc429f498beb1cb113
HarborLibrary/History-General: 635ad1b4b32e1b5176e3da17de5fceeb1e40a545
HarborLibrary/Social-Sciences: 37922fe6bf597bb759f9dc8c7bcafec42e3d2f91
HarborLibrary/Military-Science: f7e2269b523d255d1fda7a06310cf936ff391fae
HarborLibrary/America-History: a0b220e7c6737905efa40f1526ee12855586aa8e
HarborLibrary/Asia-History: 81f569169a304b73f18b7ae5f5a00c6678c1b95e
HarborLibrary/Commerce: 9cbd104090f1105e133c999f3d9fa6ad27b8a9a0
HarborLibrary/Political-Science: 1bc835ac1625cf76734afc774fc937ee89c888d6
```

Source URLs:
- https://github.com/chenggaw/mingchaonaxieshier
- https://github.com/HarborLibrary/Chinese-History
- https://github.com/HarborLibrary/Europe-History
- https://github.com/HarborLibrary/History-General
- https://github.com/HarborLibrary/Social-Sciences
- https://github.com/HarborLibrary/Military-Science
- https://github.com/HarborLibrary/America-History
- https://github.com/HarborLibrary/Asia-History
- https://github.com/HarborLibrary/Commerce
- https://github.com/HarborLibrary/Political-Science

Resolve each branch's actual current COMMIT when acquiring a file. Store both commit and blob identities; do not label the above tree SHA as a commit SHA.

## 2. Source roles

- Chinese-History: Chinese periods/events; separate ancient/modern using the project's actual periodization.
- Europe-History, Asia-History and non-US American events: world coverage.
- America-History: US stories where appropriate; other American events remain world.
- History-General: historical context, comparative history and source leads.
- Commerce: economic history, organizations, enterprise, financial decisions and supporting economic concepts.
- Social-Sciences and Political-Science: institutions, governance, social change and analytical perspectives. Attribute authors' arguments; do not turn interpretive claims into neutral facts.
- Military-Science: one optional subject among the others; no war quota or priority.

Prefer a small diverse shortlist over a volume target. Maintain author/translator/edition, genre, primary/secondary status, standpoint and source-dependence information. A translated edition of the same text is not independent corroboration.

## 3. Special case: mingchaonaxieshier

This repo is an mdBook-style chaptered Markdown text:
- src/SUMMARY.md provides the reading order.
- Chapter files are under named volume directories; use SUMMARY order, not lexicographic filesystem order.
- .gitattributes, book.toml and directory structure are source data. Do not execute its scripts/build just to read text.
- Add a small Markdown intake adapter over the existing text pipeline if useful. Retain volume/chapter heading, source file path, paragraph, normalised offset, repository commit and file hash. Do not invent page numbers.
- Use the work for engaging episode discovery and the author's account. Verify the particular historical event against appropriate supporting sources before treating novelistic dialogue, thoughts, motives, dramatic framing or causal explanations as established fact.
- Produce an original narration; do not imitate or copy the author's distinctive storytelling.
- Inspect edition/completeness in the actual text rather than assuming that chapter organisation establishes completeness.

## 4. Acquisition, deduplication and preservation

Continue the existing metadata-first, selective-download workflow. Do not clone all nine libraries to the Pi; current listed file content alone is about 4.71 decimal GB before Git history and extracted caches.

- Inventory remote paths, default branches, file sizes, Git object IDs, formats and candidate titles.
- Deduplicate exact blobs across repositories, and separately normalize title/author/translator/edition/volume. Merge source locations while retaining provenance. Different volumes of a work are not duplicate books; a different translation is not automatically the same file or a second independent source.
- Prefer a clean EPUB/TXT/Markdown version for the same verified edition; then text-based PDF. Mark scanned PDF, CHM, MOBI/AZW3, DJVU and archives as deferred unless an existing safe adapter can handle them.
- Do not treat a larger scan, an incomplete edition or a multi-book compilation as interchangeable with a clean complete text. History-General explicitly contains a file labelled missing chapter 8: exclude incomplete copies when a complete usable edition exists.
- Validate actual download signatures and sizes: Git/LFS pointers and HTML challenge/error pages are not books. Use bounded requests, per-file limits and checksums.
- Preserve the existing small pilot limits (<=50 MB/file, <=200 MB initial acquisition), actual disk/RAM checks and bounded parser subprocesses. No bulk OCR.
- Keep selected full books and extracted text private; public Git/site outputs remain original prose, bibliographic records and appropriate quotations.
- Record upstream URLs plus any actual fork URL and snapshot status. Continue already-authorized preservation work from task 05; do not claim a new source is forked or independently backed up merely because its URL is in this document. Do not overwrite or delete existing forks or local work.
- The new Drive folder remains a separately supplied private source. Do not copy its URL/listing into public reports as part of this public-repo discovery.

## 5. Concrete trial: from source to readable articles

Do not let more catalogue work delay the email/site test or the P1 repairs in docs/reviews/AFK_TEST_REVIEW.md.

After current necessary repairs:
1. Build a small cross-topic shortlist (roughly 12–20 works) from these and the already ingested sources. Choose for usable evidence, quality and category gaps; do not arbitrarily prefer military material or only famous leaders.
2. Validate actual Markdown intake from one relevant Ming-history chapter and at least one EPUB/TXT or text-PDF candidate from HarborLibrary, where accessible and appropriate. Document parser/extraction failures honestly.
3. Select a few concrete EVENTS: what happened, who acted, constraints, the sequence/outcome and what can usefully be learned. Book summaries and philosophical arguments alone are discovery aids, not event evidence.
4. Read the complete relevant episode/chapter, including its ending and context before/after chosen excerpts. Use the source-context/absence-claim safeguards already requested. A model must not infer "the source does not say" from an excerpt gap.
5. Locate evidence by stable chapter/page/paragraph references and source hashes. Add necessary verified background rather than making names or circumstances incomprehensible.
6. Complete one or two new, varied book-derived bilingual articles through drafting, bounded named final review and valid admission, while respecting remaining job/model limits. Distinguish a title lead, parsed file, evidence-backed candidate, draft and admitted final.
7. Aim for roughly ten minutes in EACH language, idiomatic English with factual/analytical parity, useful reflection with limits, an open question, example reasoning and further reading. Do not pad weak evidence to hit a count.
8. Inspect final Chinese/English and real rendering. Model admission is not reader approval; reader feedback stays pending until actually received.

The catalogue is broad enough for a meaningful trial. Prioritize demonstrable article quality and traceability over maximizing repository or book counts.

## 6. Report and integration

Safely sync current PR #1 and preserve concurrent work. Reuse the current books/discovery interfaces; avoid a second competing pipeline. Record actual source acquisition locations and status in the private manifest, and public bibliographic metadata in the appropriate project catalogue.

Push implementation/tests and an update covering:
- remote inventory vs unique works vs actual acquired/parsed files;
- verified source commits/hashes and stable locators;
- duplicate/incomplete/unsupported-file handling;
- evidence contexts and corrections;
- actual admitted article outputs and reading-time estimates;
- real mail test state and no-duplicate behavior;
- honest inventory coverage and remaining blockers.

No automatic public launch, main merge or production timers. Do not send another real email just to announce the new book sources.

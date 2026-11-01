# Additional book sources and preservation handoff

This supplements the active AFK test/review tasks. It does not replace their priorities or authorize an official launch, main merge or production timers. The owner reports that mail configuration has been completed and already handed to the active Claude; verify that actual state without printing secrets, rather than repeating stale missing-configuration assumptions.

## Sources and inspected facts

### yaoxingle/bo-guan-yue-qu
https://github.com/yaoxingle/bo-guan-yue-qu

Inspected Git tree main at 1b0d81a1ada44c920d5c19798447616127cec825:
- 474 PDF blobs in 22 topic directories, plus README and a link-list TXT; the tree response was not truncated.
- Current PDF/source blob inventory is about 4.02 GB in decimal bytes; README's "480 / 4.61 GB" is not the exact inspected count.
- Actual PDF objects are listed in Git, not just third-party download links. Download/extraction has not been verified here.
- Start with 12-历史与世界格局, 13-人物传记, 14-企业传记与商业史; use 02-经济金融与理财 and 17-科学科普 as additional topic leads.
- Observed titles include 万历十五年, 叫魂, 帝国定型, 中国财政史十六讲, 经度, and 巴菲特致股东的信. These are file/title leads, not reviewed content or factual endorsements.
- Some books have duplicate versions and some filenames identify fictional or interpretive works. Verify the actual edition, genre and extraction.

### stevenspage/english_ebooks
https://github.com/stevenspage/english_ebooks

The actual default branch is master, not the /tree/main URL originally pasted by the owner.
Inspected master tree a6823f5cbd083c215c6a4948892a698342b8158d:
- 68 EPUB blobs under ebooks/, alongside book_info.json and README; tree was not truncated.
- Actual EPUB objects are listed in Git. File parsing, integrity and contents have not been verified here.
- Includes fiction and nonfiction. Observed nonfiction candidates include Shoe Dog, From the Ground Up, The Psychology of Money and The Admirals.
- Classify memoir/biography, interpretive nonfiction and fiction separately. Fiction cannot evidence an asserted historical episode; memoir claims need attribution and context.

### Owner-provided Google Drive folder

The owner supplies its exact URL separately in the private handoff. Do not copy the folder URL/id into the public project repo or public reports without an explicit intention to share it publicly.

Its directory listing, ownership, contents and download permissions have NOT been verified in this review. Inspect only the specified folder. If publicly readable, inventory file metadata and test one selected file. If login or permission is needed, record that requirement and continue with the Git sources. Do not search the owner's unrelated Drive or publish account/session data.

## Preservation: fork plus selected private file backups

The owner asked whether to fork the two public Git repositories to protect against upstream deletion. Recommendation: yes, then keep an off-GitHub copy of selected useful files.

If the owner forwards this as an execution handoff:
1. Inspect the existing authenticated gh identity and whether miraclestar43 already has forks. Do not print credentials.
2. Fork both repositories into miraclestar43 using the existing GitHub session/gh CLI. No new account or paid service. No overwrite/delete if a same-named repository exists; inspect whether it is already the correct fork.
3. Fork without cloning the books onto the Pi, e.g. gh repo fork OWNER/REPO --clone=false. Inspect supported flags first. Verify each fork's parent, URL and default branch; report actual results.
4. Resolve the fork's actual current default-branch head. Preserve an initial dated Git tag/ref if appropriate, and record the snapshot commit in the local acquisition manifest. Do not sync upstream deletions blindly or reset local work.
5. Use each fork as the stable retrieval source and retain original upstream attribution. Do not modify or execute upstream code.
6. Fetch selected needed raw files individually, avoiding a multi-GB full-history clone on the Pi. Record repository/ref/path/blob hash, bytes, download result, local file SHA-256 and version metadata. A file fetched from later upstream state must record that different ref.
7. Keep selected full books/extracted text in a private directory outside the public project Git. Public forks are public, not private storage; do not add credentials, private Drive listings or new private material there.
8. Forking preserves Git-stored files; it does not back up external download links, Drive folders or third-party hosts. Check whether any selected object is an LFS pointer, incomplete download or HTML error body before calling it a preserved book.
9. Keep independent private backups of the selected useful files where storage permits. A local clone on the same Pi alone is not a second-device backup; record the actual backup location/status honestly.

Official GitHub preservation reference:
https://docs.github.com/en/pull-requests/reference/forks
When a public upstream is deleted, an active public fork becomes the new upstream for the network; public forks remain public. This is useful protection against ordinary owner deletion, not a claim that GitHub is an independent archival service.

## Intake implementation and next deliverables

- Lower ebook-treasure-chest's acquisition priority; retain its existing metadata as optional discovery. Do not delete existing ingested sources or provenance.
- First inspect the new repositories' manifests/tree remotely, deduplicate, classify and shortlist roughly 10–15 useful titles across topics. Avoid bulk acquisition.
- Prefer the existing EPUB/TXT parser. Add a SMALL text-based PDF path for bo-guan-yue-qu, because otherwise the whole Chinese source is outside current parser support.
- For PDF: inspect document/page limits and actual text quality; extract within bounded subprocess/resource limits. Keep 1-based PDF page index plus paragraph/location and file hash; record printed-page labels separately only when verified. Spot-check CJK readability and page-order integrity. If it is scanned or garbled, mark needs_ocr and move on instead of silently claiming usable text or starting full-book OCR.
- Prefer smaller files first, reuse existing initial <=50 MB/file and <=200 MB total pilot limits, and check Pi disk/RAM. Do not clone four GB of books just to choose one episode.
- Select a small Chinese PDF and an English nonfiction EPUB if accessible/use is appropriate. Verify acquisition and extraction, author/edition, chapter/page locations and relevant surrounding narrative, including the episode's outcome.
- Use the source-context/absence-claim safeguards in AFK_TEST_REVIEW.md. A digitized modern book is not automatically independent corroboration and a book author's interpretation is not an unqualified historical fact.
- Full text stays private; public output is original writing with bibliography and appropriate quotations. Preserve topic breadth; no war priority.
- Produce at least one real new book-derived article through evidence, drafting, bounded final review and valid admission. Report acquisition, parsing, candidate and final-article outcomes separately. Keep a blocked title from stalling useful work.

Finish the already-authorized one-test email/site task first or continue independent book work while it is genuinely blocked. Keep the same test identity, prevent duplicate accepted/unknown sends and keep all production timers off.

Report fork URLs and verified parent/head, actual acquired file counts/bytes, failed accesses, parser evidence, article results, current coverage and meaningful tests. Do not call directory listings or mock fixtures real-book ingestion successes.

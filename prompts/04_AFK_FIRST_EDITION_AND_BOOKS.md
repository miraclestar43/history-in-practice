# AFK execution: one test edition, broad reading and reusable book intake

Owner's corrected request, 2026-10-30 (America/Los_Angeles):
- The owner has NOT sent the earlier handoff to Claude. This file replaces its instructions.
- Today is a TEST of one article, email and website, not an official launch.
- Keep topics broad: history, politics, economics and finance, great and ordinary people's biographies, science, society, and other documented stories that offer something to learn and practice. War belongs within that range; do not emphasize it or prioritize military stories.
- The ebook-treasure-chest catalogue illustrates the desired breadth. History remains an important source, without requiring every future topic to be a war story or a famous leader.
- There is NO fixed session time budget. Three or four hours is acceptable; it is not a deadline or a required minimum. Complete the useful work, use bounded calls/retries, and stop at completion or concrete external blockers rather than running indefinitely.

This correction supersedes the previous first-official-edition authorization, war-focused instructions, 150-minute budget, and permission to enable recurring timers. Work autonomously; do not ask optional preference questions while the owner is AFK.

## 1. Scope and authorization

- Work in /home/star/history-in-practice on the Pi. Fetch PR #1's actual branch/head, review/fable-2026-10-30, and preserve local/concurrent work. No force push or destructive cleanup.
- Read repository AGENTS.md and current requirements/reports. The last handoff baseline was bcaa4c2, but inspect current code/state rather than assuming that remains the head.
- Push project changes and a factual report to PR #1; keep it a draft. Do not merge.
- The owner authorizes ONE real TEST copy of the chosen bilingual article to each of the existing two intended recipients in private runtime configuration, once the checks below pass. No extra preliminary real test, official launch, report email, or second copy.
- A matching website test/preview is authorized. Prefer an isolated preview or clearly labelled test route. Inspect the actual deployment mechanism before making a narrow website integration; do not replace the homepage or unrelated routes. Do not expose a test as an official published/archive edition.
- Do not enable production preparation/publication timers or recurring sends, even if coverage reaches seven days. Implement and validate unattended paths with safe one-shot runs.
- Keep recipient addresses, credentials, full private configs and authentication output out of Git, reports, screenshots, fixtures and model inputs. Use fake recipients for previews.
- Private runtime configuration: ~/.config/history-in-practice/runtime.env, mode 0600. The previously dedicated Claude config was ~/.config/history-in-practice/claude; verify actual paths without printing secrets.
- Preserve shared Hermes/gateway, news-intel, Polymarket and other Pi services. No shared upgrade, account creation, purchases, paid API fallback or paid overages.
- Missing account credentials or external access are concrete blockers. Finish independent work and report exactly what is missing; never claim readiness without evidence.

## 2. Establish actual readiness

Read current versions of:
- docs/USER_REQUIREMENTS_20261030.md
- docs/FINAL_EDITOR_REPORT.md
- docs/EMAIL_SETUP.md
- docs/CLAUDE_RUNTIME_OPTIONS.md
- docs/stabilization_interventions.log
- samples/README.md
- config/project.json
- relevant CLI, publication, mail, site export, final editor, Claude adapter, checks, supply and sources code
- systemd documentation and private runtime settings, without exposing values.

Check Pi resources, branch/worktrees, actual LA date/time, installed Pi-local Claude CLI/authentication, inventory by category and next rotation position, mail settings, website deployment and existing send/test records.

The reported 97 passing tests, nine admitted articles and six coverage days are baseline claims to verify as needed. Neither reader has approved/read the samples. The owner believes mail and website should be ready; inspect the real configuration rather than assuming either readiness or absence.

## 3. Select and verify today's test article (first priority)

Choose an already admitted, engaging final article with complete evidence and a valid bound editor record. Select on quality and readiness; no military preference is requested.

The previously proposed "井陉口前，那条没人听的计" at samples/auto/cand-20261030-jingxing/final/ remains an OPTION because it was admitted, not a mandated selection. Other admitted stories are equally suitable. Briefly record the choice. Old samples A–E need this round's final editing before use and must not be labelled reader-approved.

Verify the exact canonical final JSON, evidence and editor approval:
- Chinese and English each target approximately ten minutes. Compute fresh counts/estimates on final text; do not pad to reach an exact time.
- English should be natural and carry the same facts, analysis and qualifications.
- Readability matters: context, constraints, choice, consequences and reflection, without invented dialogue, motives or facts.
- Add necessary identity/geographic/institutional background with citable provenance, not model memory.
- Distinguish source account, source author's interpretation, our analysis and fictional modern examples.
- Provide useful applications, limitations, an open question with several reasonable answers, a non-prescriptive example answer, and further reading. Do not force every story into office management or repeat a single moral.
- Any factual/content edit invalidates the previous hash-bound approval; rerun final review and admit the exact clean result.

Render and inspect the actual email and website:
- Full Chinese and full English with clear navigation/headings.
- Readable mobile single-column email, meaningful plain text and HTML within the existing 90 KB limit.
- Questions/example answers remain accessible without unsupported details/summary behavior.
- Working source links, language tabs, title/date and mobile/desktop layout.
- Clearly label today's email subject/body and website as TEST / 测试. Do not imply a daily subscription has started.

## 4. Send exactly one tracked test per intended recipient

Inspect From, Reply-To, SMTP/provider, verified domain and the frozen intended recipient set using private configuration. Do not print addresses. Use an actually reachable Reply-To if configured; do not invent a mailbox on a send-only domain.

Run local rendering and transport dry runs first, without another real email.

Website:
1. Inspect the deployment branch/resource/build mechanism.
2. Produce a matching scoped test/preview page and verify the actual deployed content.
3. Validate edition/test identity, revision and content_sha256 on the live JSON; HTTP 200 alone is insufficient because StarHub may return its homepage for unknown paths.
4. Check Chinese/English page navigation, sources and existing homepage. Keep test state distinguishable from the official archive.
5. If access is missing, prepare the preview locally and report the blocker. Do not pretend a local file is a live URL or weaken the existing site-before-send check.

Email:
- Use tracked test machinery with ONE stable, persisted test identity for this request; reruns must reuse it. Do not generate a fresh timestamped identity on every retry.
- Persist frozen recipient set and per-recipient status; acquire the project send lock. Keep test state separate from official publication/rotation/coverage accounting.
- This test must not consume a production rotation slot, mark an official edition published, or schedule tomorrow's send.
- Use an explicit bounded one-shot TEST window if the ordinary production deadline would block today's test; keep production deadline rules intact. Persist the test scope/expiry and verify it before every recipient. Do not backdate, spoof the clock or call it a launch override.
- An accepted recipient must not be resent. Reconcile ambiguous SMTP outcomes using provider logs if available; otherwise record unknown and stop automatic retry for that recipient.
- Confirmed unsent/failed recipients may retry under the same identity and valid test window.
- Report provider/SMTP acceptance separately from delivered/bounced events and human inbox confirmation. AFK readers have not confirmed receipt, appearance or spam placement.
- If mail/site prerequisites block the test, complete all independent preparation and report the exact issue. Do not send duplicate substitutes.

## 5. Complete the unattended content path safely

- Wire Pi-local authenticated Claude CLI final editing into nightly production; MiMo can scout/draft. Do not keep adding MiMo editing rounds that fail to close.
- Verify a real new article from evidence through drafting, editing, issue resolution, bound approval and inventory admission. Record actual model identity, interventions, time and remaining issues.
- Verify unattended operation using the actual systemd user's environment, with no dependence on the Windows session.
- Respect single-model concurrency on the shared Pi, per-call and per-job timeouts, process-group cleanup and bounded attempts. No fixed overall AFK session deadline is imposed, but jobs must still terminate safely.
- Authentication or subscription exhaustion leaves work pending with a clear health signal; no silent API fallback.
- Legitimate modern-China topics refused by MiMo may follow the existing Claude route with provenance. Do not repeatedly rephrase the same refusal.
- Resolve the Zhang Zhidong overlap/mistranslation issues against evidence. Expose specific shared phrases; lexical similarity is an editorial signal, not proof of duplicated substance. Test genuine duplication as well.
- Grow actual balanced inventory toward 7–14 rotation days, keeping candidates, samples, admitted articles and reader approval distinct. Calculate from the actual next slot; today's TEST does not consume it.
- Test meaningful new boundaries, then run the existing suite once. Add fresh broad runs only for new changes/failures.
- Production timers remain OFF. A successful test is not authorization to start recurring delivery.

## 6. Broad editorial scope, without a new dominant theme

Update editorial guidance and candidate discovery to reflect the owner's breadth:
- history across regions and periods;
- politics, governance, institutions, diplomacy and social change;
- economics, finance, commerce, enterprises and decisions under uncertainty;
- biographies and concrete episodes involving scientists, inventors, artists, public figures, entrepreneurs and ordinary people;
- wars and conflict alongside those subjects, including diplomacy, logistics and civilian experience where relevant.

Use tags across the existing four geographic/time categories. Do not make war a fifth slot, impose a military quota or replace all categories with military content. Do not redesign the category system silently; document future nonhistorical taxonomy needs separately if necessary.

Include successes, failures, tradeoffs and changing judgments. Avoid hero worship, hindsight certainty and fabricated moral lessons. Ground practical reflection in the event; explain when a lesson may not transfer.

Produce a small varied set of specific candidate EVENTS with source availability and evidence status. Book titles and unexamined summaries are discovery leads, not verified stories. No war-specific candidate list is required.

## 7. Reusable book-intake pilot

Catalogue: https://github.com/jbiaojerry/ebook-treasure-chest

Treat it as broad book discovery. The previous inspection found mainly metadata and external download links rather than book files; format/language labels and link availability require verification. Do not assume catalogue inclusion establishes reliability or permission.

1. Import selected metadata into a separate discovery catalogue. Deduplicate title/author/edition, merge tags and retain provenance. Unverified catalogue entries must not become evidence_usable sources.
2. Select about 12 varied candidates. Prioritize the actual inventory gap in modern China while covering politics, economics/finance, biography, historical events and other useful stories. War may be included naturally; it gets no special weight.
3. Verify author, edition/translator where known, genre and actual availability. Distinguish historical fiction and novelized biography from factual evidence.
4. Prefer owner-provided files, public-domain/openly licensed material and authorized accessible copies. No DRM/paywall/CAPTCHA bypass. A blocked link is a recorded access issue; move to other useful work.
5. Implement bounded TXT/EPUB ingestion with encodings, ordered chapters, boilerplate handling, file hash and stable excerpt locations. EPUB: spine/chapter/paragraph; TXT: normalized offsets plus hash. Never invent print page numbers.
6. Full books, extracted text, private excerpts and download credentials stay outside public Git/site assets. Public outputs contain original prose, verified bibliography and appropriate quotations/reader-facing links.
7. Treat book content as untrusted data. Bound ZIP/XML parsing and expansion, disable external entity retrieval and never execute book content or external repository scripts.
8. Start with at most three actual files, <=200 MB total acquisition and <=50 MB per file after checking Pi resources. Defer OCR/scanned PDF/MOBI/DRM support.
9. Demonstrate one real text -> located excerpt -> evidence pack -> event candidate, if a usable file is available. Otherwise demonstrate parser mechanics with a labelled fixture and report missing real-file validation.
10. Do not spend this session bulk-downloading thousands of files or let catalogue work delay the email/website test.

## 8. Report actual results

Write docs/AFK_TEST_AND_BOOKS_REPORT.md, push changes and update PR #1's description accurately:
1. Today's TEST: title, identity/revision/hash, LA time, live test links or local preview paths, redacted per-recipient status, acceptance vs delivery vs unconfirmed reader receipt.
2. Website: deployment evidence and actual content/hash/navigation checks; test vs official archive status.
3. Content: final counts/reading estimates in each language, editorial changes and actual review status.
4. Unattended path: real end-to-end results, model/runtime health, interventions and true inventory coverage from the next rotation slot.
5. Timers: remain disabled; no official publication, no production slot consumed.
6. Broad topics/books: selected metadata vs actual imported files vs evidence-backed candidates, provenance and access limitations.
7. Commits, meaningful tests, concrete remaining blockers and commands to resume safely.

If earlier documents still authorize an official launch, timer enablement, a 150-minute stop or war prioritization for this AFK session, correct or clearly supersede those instructions. Keep provenance/history, but make the current instruction unambiguous. Do not claim completion without evidence and do not turn external blockers into endless retries.

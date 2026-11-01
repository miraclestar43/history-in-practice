# AFK test and books review — 6c08cd8

Reviewed 2026-10-30 (America/Los_Angeles). Scope: report, current PR metadata, and selected CLI/test-run/final-editor/evidence/source/mailer/config paths. This is a targeted review, not an independent rerun of the reported 118-test suite. No Pi access, live mailbox inspection, production deployment or real email send was performed here.

## Assessment

The report supports an important implementation milestone: a preview and a Pi-local unattended editor path exist, with honest intervention and defect records. It does not establish reliable autonomous editorial quality. Of four new articles, two needed an extra operator-triggered attempt; of the other two, one was later found factually wrong and requeued. This is too small a sample to estimate a long-run success rate.

The reported 12 rotation days is internally consistent with A3 W4 M3 U3 and next category A. It is an operational status count, not independent confirmation that every admitted article is accurate. The other new finals' absence claims remain unaudited against their source context.

Keep the test-only scope, broad topics, draft PR, production timers off and main unchanged.

## P1 — incomplete excerpts can produce false conclusions, even after final review

The reported Wu Qi defect is substantive: a paragraph claims the source does not give the Lu ruler's response, while the supplied excerpt stops immediately before that response. Hashes and verbatim quotation checks only establish consistency with the chosen text.

Decision recommended:
- Fix Wu Qi rather than drop the candidate solely for this repairable defect. Preserve its requeue and correction history.
- Inspect the complete relevant episode/chapter in the cached source, add the omitted sentence AND sufficient context/outcome, repair dependent interpretations and both languages, and obtain a fresh hash-bound final admission.
- Audit all schedulable articles for absence assertions, in Chinese and English, including prose, uncertainty notes and further-reading descriptions. Prioritize the other three new finals explicitly identified in the report. Flag candidates for inspection rather than declaring every keyword match erroneous.
- Do not merely replace every false "the source does not say" with "our excerpts do not say". That narrower statement may be literally true while still concealing a readily available answer and misleading the reader.
- For an unnecessary absence assertion, remove it. For a necessary assertion, inspect the complete identified relevant source unit and describe only that scope accurately. "This chapter does not explain X" is narrower than "history does not record X"; neither follows from a keyword miss.
- Record source identity/edition, cached text hash, reviewed unit and spans, completeness limitations and reviewer finding. Missing/truncated text or unreviewed relevant context means unresolved, not verified absence.
- Do not send whole books into every call. Use full relevant chapters/episodes or bounded retrieved context; if context exceeds the call budget, review recorded segments with coverage and explicit unresolved areas.
- Extend the evidence preparation stage to inspect surrounding context and the event's conclusion BEFORE drafting. This addresses misleading positive narratives as well as absence claims.

The automatic gate must consume the context-review result; a prompt-only instruction is insufficient. A heuristic detector is triage, not proof that all possible absence language was captured.

Meaningful regression cases: the decisive answer immediately after an excerpt; paraphrased Chinese/English absence wording; a scoped genuinely supported statement; a missing/truncated source unit; expansion of evidence invalidating an earlier admission. Validate at least one real repaired article end to end.

## P1 — TEST preparation/send does not enforce current source admission

Code: src/history_in_practice/cli.py cmd_test_edition; src/history_in_practice/testrun.py create_or_load/send.

The CLI routes preparation to create_or_load without an admission check. create_or_load reads arbitrary supplied JSON, checks its labels/hash consistency and persisted identity, but does not consult the edition's admitted status or final-editor record. send checks the preview, window and SMTP configuration, but does not revalidate source admission. Thus a previously admitted source can be requeued after test preparation and still reach the transport. Matching the preview hash does not establish current editorial eligibility.

Independent minimal reproduction:
- Executed the exact testrun.py from 6c08cd8 in a temporary Python harness with SQLite.
- Stubbed rendering, HTTP verification, mail transport and completion helpers; zero network/SMTP calls.
- An unregistered source with a self-consistent content hash was accepted by create_or_load.
- After inserting that source into an edition table as pending_review, send reached the mocked send_edition transport.
- Outputs: "UNREGISTERED source accepted by prepare: True"; "REQUEUED source reaches mocked transport: True".

This demonstrates the missing admission dependency, not a real bad email delivery, and does not allege that the Snow article itself is defective.

Fix:
- Use the same current editorial eligibility verification as the canonical admission/publication path at preparation and again under the send lock immediately before first/remaining recipient sends.
- Verify canonical source identity, revision/content hash, actual final-editor record and evidence binding, plus current eligible state. Merely trusting a status field inside an arbitrary JSON file is insufficient.
- A requeue/revocation, missing record, changed evidence or changed source must block unsent recipients, including after a partial test send. Retain accepted/unknown delivery rows and never resend them.
- Ensure the guard's placement cannot become stale between its check and use; coordinate with editorial state mutations where necessary.
- Add tests for an unregistered draft, prepared-then-requeued source, changed evidence/record and a still-valid admitted source. Preserve existing no-duplicate and preview-content tests.

No need to rebuild the whole test subsystem.

## Retry decision — three bounded final-editor attempts is reasonable

Recommend final_editor.max_attempts = 3, while retaining per-call/process-group bounds, per-job deadlines and unchanged factual/admission thresholds. This is a modest operational change, not a fix for incomplete evidence and not a quality guarantee.

Code detail: _final_one currently runs an initial attempt and at most one immediate continuation. Changing the limit from 2 to 3 alone permits a later queue invocation to use the third attempt; it does not make all three run within that invocation. Implement or explicitly document the intended behavior. For unattended supply, prefer a bounded loop that respects the remaining job deadline before each continuation.

Carry forward the previous text and unresolved issues rather than restarting; distinguish article attempts, revision rounds and schema retries. Authentication/subscription failures stop the queue and do not use up the editorial allowance. After three genuine attempts, leave pending with a clear diagnostic; do not require routine owner approvals for extra attempts or silently relax issues.

The report's reference to an owner-imposed 150-minute session budget is stale. The owner imposed no fixed AFK time limit. Explicit bounded nightly jobs remain appropriate; document their configured limits separately.

## Length and books

- Repair the ~6-minute Chinese Zuo Zongtang draft toward the requested ~10-minute experience with supported context and analysis; do not pad. If the episode cannot sustain it, keep a short-item flag separate from readiness for the default ten-minute edition.
- Review English pacing and bilingual information parity on the actual final versions. Do not demand identical word counts or exact reading times.
- Book ingestion is a real technical pilot; the Curie candidate still needs drafting and final review. Demonstrate one complete book-derived article rather than enlarging the catalogue first.
- Catalogue metadata is discovery. An open original or a different translation must be identified as that actual source, not presented as the catalogue's modern book. Maintain source dependence/attribution and private full-text storage.
- Preserve topic breadth. No war priority or quota is needed.

## Email — concrete owner configuration, not another development milestone

The report states no real connection occurred and SMTP_PASSWORD / EMAIL_REPLY_TO are missing from the project's private file. Public DNS checks do not by themselves establish whether a Resend account/domain entry exists: verify actual provider status during setup.

The owner needs to:
1. Add/verify read.starhub.vip in Resend and put only its actual returned DNS records in Cloudflare.
2. Create a sending key and save it privately as SMTP_PASSWORD; set EMAIL_REPLY_TO to an inbox the owner reads. Do not request the key in chat or Git.
3. Keep EMAIL_SEND_ENABLED=false and production timers off.
4. After the test admission guard is fixed, run doctor, inspect the persisted test status, renew the unused window only if necessary, and send under the SAME test-20261030-snow-water identity.
5. Confirm both inboxes/spam folders, bilingual rendering, authentication headers and reply routing.

Official references checked during this review:
- https://resend.com/docs/send-with-smtp — verified domain and API key prerequisites; username resend, password API key, port 465 implicit TLS.
- https://resend.com/docs/dashboard/domains/introduction — each sending subdomain is added/verified separately.

A receiving mailbox at history@read.starhub.vip is not required for this sending setup; the project's mandatory Reply-To provides a reachable feedback destination.

## Follow-up execution and evidence

Fix the two P1 issues before resuming real test sends. Audit affected inventory, repair Wu Qi, implement bounded three-attempt behavior, improve the short Chinese article and produce one book-derived final. Report updated coverage after any quarantines/corrections; do not inflate it with fixtures or unreviewed candidates.

Push changes and update the report/PR title and description (the current title still mentions 97 tests / six days). Record actual tests and interventions. Keep PR #1 a draft, production timers off, main unchanged and delivery limited to the already-authorized single TEST per existing recipient. A successful test remains separate from official launch authorization.

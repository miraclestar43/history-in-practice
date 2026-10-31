> **Priority superseded by the owner (2026-10-31):** See [07_READER_FIRST_CHINESE_SAMPLE.md](../../prompts/07_READER_FIRST_CHINESE_SAMPLE.md). The owner had not sent this handoff and explicitly chose to park Snow and produce one readable Chinese story first. Snow repair, arithmetic work and its notice must not block that deliverable. Technical findings below are retained as history, not current task ordering.

# Running repair queue review: publish the known-error notice separately

Date: 2026-10-31 (America/Los_Angeles).
Code inspected: d3c2d981bdc0390847d12232d79c94b051b5ed76, PR #1.
The owner's progress update reports the queue resumed after an approximately five-hour interruption; chains 3–5 are running one job at a time. This review does not access the Pi or independently confirm live process state, notifications, or completion. Do not stop/restart those jobs just to incorporate this document.

## Assessment

- d3c2d98 does add explicit source-absence rules to final audit/verify/revise. The direction is correct.
- At the inspected pushed head, final_edit._view still supplies the evidence pack and article; carried_context passes prior context findings/expanded evidence only when its hashes match that exact base. Do not assume the editor has seen a whole source merely because a later context reviewer did.
- The reported 156 passing tests are not independently rerun here.
- Keep existing admissible work; do not demote it solely because another draft is bad. Pending items remain pending until their exact final content passes.

The next step should not be another wholesale increase in attempts. Correct the fact inputs and unblock the narrow reader-facing correction first.

## 1. Publish an additive known-error notice now, without waiting for the entire Snow article

A dated erratum/under-review banner is a different artifact from a fully repaired article. It can state the already-confirmed error and the ongoing review without asserting that the rest of the article is correct. Its small factual payload must be checked, but it need not wait for all of the long article's statistical, narrative and stylistic questions.

Suggested Chinese notice:
> 更正提示（2026.10.31）：此前测试稿称本篇证据中没有当时外部独立核查，这一表述不准确。斯诺书中还记载了登记总署组织的后续供水资料调查，并称其结果与他较早的调查一致。这不等于所有数字都经过独立审计。全文仍在复核，修订版尚未获准发布；请暂勿据测试稿引用其数字或结论。

Suggested English notice:
> Correction notice — 31 October 2026: The test article's statement that its evidence contained no contemporary outside independent check was inaccurate. Snow also describes later water-supply returns collected through the General Register Office and reports that they agreed with his earlier inquiry. This is not an independent audit of every figure. The article remains under review; a revised version has not yet been cleared. Please do not rely on the test article's figures or conclusions in the meantime.

Primary source checked:
https://www.gutenberg.org/files/72894/72894-h/72894-h.htm
Printed pp. 86–88, passage introducing Table X. Cross-check against the existing cached edition before attaching locators.

Use the existing isolated TEST preview route, not main or starhub.vip production. A small static bilingual notice or existing-banner extension is sufficient; do not build an elaborate correction platform first.

Preserve the sent article and its immutable body/revision/hash and delivery rows. A notice can be separate metadata keyed to the sent edition/revision. Do not make an old hash appear to describe new text.

The original email may point to an immutable Cloudflare deployment. A new branch-alias preview does not retroactively change that old deployment. Report precisely which URL now displays the notice and give the user that URL here; do not claim the email's existing immutable link has changed unless verified.

No replacement TEST, duplicate send or new identity. This document does not authorize any new email.

## 2. Resolve the arithmetic from evidence, not repeated model guessing

Independent arithmetic performed here:
- 2353 / 40046 * 10000 = 587.574289566998.
- 302 / 26107 * 10000 = 115.67778756655304.
- The ratio of those two recomputed rates is about 5.0794.

The Gutenberg transcription also prints 537 in the sentence after Table X. That establishes a conflict in that transcription, not proof of whether the specific printed edition, OCR or a later transcription introduced it. A visual inspection of the relevant scan page was not completed in this review; do not label it an original printing error without that check.

Decide one clean editorial treatment:
- If later-period detailed rates are unnecessary for this story, omit those disputed secondary numbers from the reader's narrative, while retaining the valid fact of the later registration inquiry and the issue in the private evidence ledger.
- If the numbers are necessary, explicitly distinguish "source prints X" from "computed here from source operands gives Y", with the actual operands, period and denominator. Add this verified derived result to the evidence/calculation record so an editor is not asked to invent a number outside its pack.
- A source quotation of 537 may be historically accurate as a quotation while using 537 as a verified computed rate is mathematically wrong. Do not silently replace a quoted primary-source number or make the evidence agree by editing it.
- Remove/qualify the sweeping assertion that ALL figures used can be recomputed. State the actual scope of checks completed and flag unresolved ones. Do not claim "clearly legible" means accurate.

Do this once deterministically for the numbers the story actually uses, BEFORE the next model editorial pass. Include rounding tolerance and units. Do not demand exact equality for legitimately rounded historical rates.

A large new numeric-audit subsystem is unnecessary for this immediate repair: a small explicit fact/calculation ledger plus arithmetic checks for used values is enough.

## 3. Freeze a compact factual core; avoid turning every discovery into more prose

The inspected Snow limits.0 is now a very long paragraph containing registrars, Whiting, dates, district qualifications, estimated populations and several table bases. That repeats the reader's complaint: too many names, numbers and institutions before the reader can retain the story.

- Keep all relevant evidence and the complete source context in the editorial material.
- Put only the limitations that materially change the story's interpretation in the main narrative.
- Move the audit trail/table provenance into optional end notes if useful; do not require a reader to consume the full repair log.
- Do not add every newly found qualifier as a fresh detailed claim that creates another round of factual and bilingual checking.
- The note's "All of this is known only through Snow's book" / "这些情况都只能通过斯诺的书得知" is still a claim about universal knowledge. If the intended point is what THIS article consulted, say "本文对上述细节主要依据斯诺的记述" / "This article follows Snow's account for those details." Do not turn a source-selection limitation into a claim about what others could know.
- Stage the work: verified fact core and evidence -> minimal factual repair -> final/context verification -> reader-focused revision on the corrected text -> fresh checks on the exact changed final. Preserve every necessary binding; avoid unnecessary full rewrites.

Retain the new "没事儿多读书" title/date format, approximately ten minutes in each language, and China-led flexible four-of-seven topic preference. Do not send a second draft simply to demonstrate the new name.

## 4. Close the editor/context information gap without sending whole books to every call

- Construct one compact issue/fact packet per article from the already completed context review: exact disputed sentence, relevant complete episode ending, required extra excerpts, confirmed source scope and known numeric derivations.
- Pass this packet into the final editor BEFORE its next revise call, with provenance/evidence IDs. Do not keep asking an evidence-pack-only editor to discover facts outside the pack, then penalize it for lacking them afterwards.
- Preserve the existing carry-forward hash checks. A stale context finding must be revalidated or explicitly rebound, not silently treated as a current approval.
- Reader-unnecessary source-absence claims should usually be removed. Necessary source-absence claims need a verified named complete scope; never turn "the excerpts do not show it" into "the source does not record it."
- No lower factual threshold, blanket exception or indefinite loop. One recorded retry using genuinely corrected inputs is meaningful; identical-input retries are not a solution.
- Curie was left out of chain 3: report that clearly and schedule it after its factual packet is ready rather than losing it from durable queue state.

There is also a prompt inconsistency worth fixing at a safe checkpoint: audit/verify's readability section allows readability/note, and final_edit._issue_problems permits it, but later prompt rules say note is only for category=style. Align those statements; do not assume this inconsistency is the confirmed cause of the current failures.

## 5. Prevent another session-bound pause

A repair queue should survive the interactive development session ending.

- Reuse the existing Pi one-shot systemd/nohup arrangement as appropriate, with a persisted queue manifest/checkpoint and process identity. This is not permission to enable production publication timers.
- Store candidate, input content/evidence hashes, code/prompt version, running/pending/completed/blocked status and last result.
- Keep one model job at a time on the shared Pi and acquire the existing lock. On resume, inspect lock/PID and checkpoint before starting; never duplicate a live job.
- Apply prompt changes between articles or other safe checkpoints. A running process may cache prompt/config state: record the version actually used. Do not pause all repair work merely to prepare a new prompt.
- After interruption, automatically/explicitly resume unfinished work from the checkpoint. A notification watcher is useful, but does not substitute for durable execution.
- Keep unsuccessful articles pending with concrete reasons. Report per-article status and actual usable coverage; do not promise a fixed completion time without actual running evidence.

## 6. Next report

Lead with the live notice URL and what it actually says; then the Snow fact/calculation decision, exact repaired version if admitted, narrative before/after, a readable Chinese example, next-seven preview, real inventory and remaining blocked drafts. Distinguish operational tests from real article outcomes.

Keep PR draft, main unchanged, no production timers, no extra real email and no changes to unrelated Pi services.

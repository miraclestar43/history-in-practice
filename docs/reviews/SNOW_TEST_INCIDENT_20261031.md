# Snow TEST correction and narrow context-review guard patch

Date: 2026-10-31 (America/Los_Angeles).
Baseline inspected: c43a9b97ec21557993551a8ba7ef4cfe05d58e0d on PR #1.
The owner reports that the TEST was sent and an audit subsequently found a factual defect. This is newer than the stale PR description saying no real email has been sent. This review does not independently inspect provider/inbox state, and does not claim the running 11-article + Curie repair chain has finished or is already pushed.

## Source finding and correction direction

Primary text checked: John Snow, On the Mode of Communication of Cholera, second edition (1855), printed pp. 86–88, passage leading into Table X:
https://www.gutenberg.org/files/72894/72894-h/72894-h.htm

Snow describes a later collection of returns by district registrars, their publication by the Registrar-General, and his judgment that these later results agreed with his earlier inquiry. Some water supplies remained unascertained. This contradicts an unqualified implication that no outside inquiry/corroboration existed; it does not establish that all his earlier numbers underwent a separate independent audit.

The inspected final/article.json still contains the disputed statement in sections.limits.0 (both languages) and uncertainty_note. Do not alter only one copy or preserve the same claim in further reading/preview prose.

Suggested factual content, to incorporate naturally and then fully re-review:
- 中文：斯诺书中还记载，登记总署组织登记员收集了疫情后期的供水资料并公布结果；斯诺认为，这些结果与他对疫情早期的调查一致。部分病例的供水来源仍未查明。本文主要依据斯诺的这部著作，不应把这层来源限制说成当时没有外部调查，也不能把它说成所有数字都经过了独立审计。
- English: Snow also describes later water-supply returns collected by district registrars and published by the Registrar-General. He considered them consistent with his earlier inquiry, although some supplies remained unidentified. This article principally follows Snow's account; that source limitation should not be confused with an absence of outside inquiry or with an independent audit of every figure.

Verify these details against the project's actual cached edition and expand its evidence pack with precise locations/hashes. The Gutenberg transcription is a cross-check, not a silent replacement for the recorded source edition. If checking Table X's arithmetic or OCR, use the scan/edition and preserve actual values rather than reproducing an apparent transcription error.

## Independent reproductions

At baseline, using the actual compiled detector/schema functions:
- The Chinese Snow "no independent check" sentence was not detected.
- Its English counterpart was not detected.
- reply_schema([], {}, {}, False)({}) returned no problems.

This does not prove that an empty model review caused the sent email error. It identifies two actual false-negative/fail-open paths that could let similar defects pass.

## Narrow code patch in this branch

- Extend Chinese/English absence triage to outside/independent/third-party verification statements.
- Include actual further_reading.what/access fields in addition to optional note/why/description fields.
- Require all four context reply arrays; reject non-object rows, blank/duplicate claim IDs and supported verdicts citing nonexistent source IDs.
- Failed context-evidence additions block article readiness instead of silently recording an error alongside a clean outcome.
- Extend the context-review prompt to distinguish source count, outside inquiry, later corroboration and a complete audit; limits/uncertainty are factual assertions too.
- Update valid scripted fixtures to include the now-required episode array; add seven regression tests.

Validation completed here:
- Both changed Python files compile.
- Seven new pure detector/schema tests and the existing paraphrased-wording test passed (8 tests).
- Tests executed the actual selected Python functions/classes from the changed sources through an AST-isolated harness, including the actual editor.fields and editor.sha helpers. No model, SMTP or HTTP calls; no simplified/traditional conversion was exercised.
- The full package/runtime suite was NOT rerun in this workspace (opencc is unavailable here); run it in the Pi environment before adopting the patch. This is not a claim of eight real editorial audits.

This patch is intentionally separate from the active repair work. Do not overwrite newer local code or restart its model jobs. Inspect the diff and apply compatible changes after a safe checkpoint, using a normal merge/cherry-pick or equivalent reviewed edit.

## Required completion on the Pi

1. Keep the repair batch progressing. Record per-article final-editor and context-review outcomes; pending is not checked. Recalculate actual coverage after repairs/quarantines.
2. Repair Snow's evidence, all duplicated statements and dependent interpretations in BOTH languages. Obtain a fresh bound final review and context review on the exact corrected text. A wording patch must not retain the previous approval hash.
3. Preserve the sent TEST's immutable payload identity, revision/hash and delivery rows as historical facts. Do not replace its stored bytes with corrected text while retaining the old fingerprint, or reset accepted/unknown rows.
4. Add a separately versioned corrected article and a short Chinese/English erratum on the existing test webpage, with a correction timestamp and before/after explanation. Update both language links/index/revision/hash coherently. Keep the old immutable Pages deployment identifiable as the sent version; a moving preview alias can lead to the corrected page. Do not deploy to main or starhub.vip production.
5. Do not send another TEST or create a new test identity merely to bypass the one-copy rule. The owner already knows the correction. Any separate corrective email would need its own explicit instruction; no such email is requested here.
6. Apply the context gate to ALL real send paths, including hip send/retry and scheduled publication, not only test-edition. Verify current eligibility of the exact content and evidence before unsent recipients. Add a stale/missing-context test and preserve no-duplicate behavior.
7. Do not rely on the regex alone. The model must audit every visible field against relevant full context. A source-absence claim on partial windows needs a verified, complete named scope or remains unresolved. Positive claims can also be contradicted by omitted context.
8. Do not assume this narrow schema patch fully validates every semantic aspect of a review. In particular, explicit empty arrays do not prove that a readable source was examined; require and validate per-source episode/field coverage in the complete gate, rather than inventing arbitrary nonempty findings.
9. Update the active report and PR description to the actual sent/error/corrected state. The report link REVIEW_FOLLOWUP_20261031.md was not present at the inspected pushed head; ensure promised reports are committed.

Keep PRs draft, production timers off and unrelated Pi services unchanged.

# Stabilisation report — 2026-10-30 (Pi, Claude Opus)

Responds to `docs/reviews/POST_OVERNIGHT_REVIEW.md` (commit 8f7061d). PR #1 stays a draft. Nothing was merged or deployed, no real email was sent, and no production timer was enabled. SMTP and Cloudflare are still unconfigured; nothing below depended on them.

## 1. Summary

**All five review findings are fixed and covered by regression tests.**
- **Deploy waits:** the live check retries with a bounded wait, unfinished editions become `overdue`, and a commit made while pushing was off is pushed once it is on.
- **Inventory:** coverage is counted by rotation, and samples, pending drafts and candidates are counted separately.
- **Mail:** sending refuses empty or incomplete config and finishes only when every frozen recipient is accepted.
- **Admission:** a draft is admitted only with a record bound to its final content and evidence.
- **First test:** an explicit one-off real test entry, with Reply-To required.

The suite has **73 tests** and passes on a fresh clone.

**Candidate supply and the editor stage are now runnable jobs** (`hip supply`, `hip edit-queue`, `hip nightly`). The real runs did not close the loop:
- Two new candidates went from catalogue to evidence, draft, model edits and re-review with no hand edits. Both are still pending after the default two attempts and a 4-round experiment.
- The seven articles admitted overnight all failed a fresh bound review; after one automated edit attempt, 1 (Snow) was admitted and 6 are pending.
- The automated editor applies its edits reliably (160 applied, 2 rejected by the exact-match rule). But each fresh review raises new issues, so most drafts do not converge within the bounds.

**Inventory is 0 days of coverage** (1 schedulable article, 9 pending, 5 unapproved samples). This is lower than the overnight report claimed, because admission now requires a review bound to the final text. Coverage starts rising once samples are approved or the pending drafts get a closing editor (section 6).

Nothing was merged or deployed, no email was sent, no timer was enabled, and no article text was written by hand. Every intervention (prompt or code changes between runs) is listed in section 3 and in `docs/stabilization_interventions.log`.

## 2. Fixes, one per review finding

| Finding | What changed | Regression tests |
|---|---|---|
| **P1-1** Async deploy: one check, then silent waiting; yesterday's edition stranded | **Bounded live-check retries.** After the site commit, the live check retries with bounded backoff until the send deadline (`project.json`: `site_wait.backoff_s` ≈ 22 min, `send_deadline` 11:00 LA). A run that still waits exits **5**. A new `hip-send-retry.timer` (08:00–10:30, every 30 min) resumes it; the run is idempotent.<br>**Overdue instead of late.** An in-flight edition from an earlier day, or past the deadline, becomes **`overdue`** (terminal, alerted in `hip doctor`). It is never sent late, and the rotation continues with a new edition.<br>**Push recovery.** A site commit made while `SITE_PUSH_ENABLED=false` is recorded as `committed` and pushed on a later run once pushing is enabled.<br>**Exit codes:** 0 complete, 3 partial, 4 skipped, 5 waiting, 6 overdue. | `test_publish`: `test_async_deploy_retries_with_backoff_then_sends_once`, `test_deploy_never_lands_waits_nonzero_then_overdue_and_next_day_moves_on`, `test_yesterdays_partial_delivery_is_overdue_not_resent`, `test_push_disabled_commit_is_pushed_once_enabled`, `test_full_flow_resumes_and_never_resends` |
| **P1-2** "12 days" was 12 articles (10 days of rotation) | **Rotation coverage.** `hip inventory` now reports `coverage_days`: the consecutive days the A→W→M→U rotation can fill from `next_category`, plus editions already scheduled ahead.<br>**Separate counts.** Schedulable, samples (total / approved), awaiting approval, pending and unprocessed candidates are listed separately, with gaps per category to the 14-day target. The alert uses coverage.<br>**What counts.** Only editions with a recorded `approval` count. Samples count only after `hip approve-sample`. | `test_inventory` (reproduces the review's case: 12 articles → 10 days, gaps A+1 M+1; other start points; samples and pending excluded; empty inventory) |
| **P1-3** No ongoing supply; editor step was manual | **Candidate supply** (`supply.py`, `hip supply`, `config/source_catalogue.json`): the model proposes an episode and 15–25 excerpt anchors from a fetched text window.<br>• Anchors must occur exactly once and cut a bounded span.<br>• Overlaps with registered passages are dropped.<br>• Dedup goes through the registry.<br>• Every attempt and proposal is logged.<br>• Brief lines that cite a dropped excerpt are removed.<br>**Editor stage** (`editor.py`, `hip edit`, `hip edit-queue`):<br>• At most 2 model edit rounds per attempt and 2 attempts per draft.<br>• Each round is followed by checker, re-review of the final Chinese, and an English-parity review.<br>• Unresolved issues are carried over.<br>• The record is bound to the final content and evidence hashes.<br>**Nightly job:** `hip nightly` runs supply → prepare → edit; the `hip-prepare` template now runs it. **The fix/block threshold was not lowered.** | `test_supply`, `test_editor`, `test_registry_pipeline` (the chain with fake models) |
| **P1-4** Zero recipients could count as success | **Config validation.** `mailer.validate_config` requires non-empty, well-formed, unique recipients; complete SMTP settings; From; and Reply-To.<br>**Frozen recipient set.** The expected set (salted keys) is frozen per edition on first send. `complete` requires every frozen recipient to be `accepted`.<br>**Config changes.** A recipient removed after freezing keeps the edition incomplete; one added later waits for the next edition.<br>**Callers.** Applied in `publish-today`, `hip send` and `hip send-test`. | `test_state_mail` (`test_incomplete_config_and_empty_recipients_never_report_success`, `test_completion_is_over_the_frozen_expected_set`), `test_publish` (`test_empty_or_incomplete_mail_config_is_never_success`, `test_recipient_removed_after_freeze_keeps_edition_incomplete`) |
| **P2** Admission not bound to final content or issue handling | **Pending drafts.** `hip admit` needs `--record`: the record's content hash, evidence hash, and final review and parity results must match the article being admitted. Checker BLOCK and an unbound record are never overridable.<br>**Remaining FIX issues** need `--exception REASON`, stored as the approval.<br>**Other routes.** New articles enter only through the pipeline, or as samples (`--as-sample`, not schedulable).<br>**Legacy and manual edits.** `hip rereview` binds a fresh review to an already-admitted edition. The manual `validation/editor_pass.py` no longer marks anything `checked`. | `test_editor`, `test_cli_admit`, `test_rereview` |
| **P2** First-test steps contradictory; Reply-To "optional" | **One-off test.** New `hip send-test ARTICLE --confirm-real-email`. It works while `EMAIL_SEND_ENABLED=false`, uses a separate test edition id and a 【测试】 subject, and needs the full config.<br>**Reply-To is required.** The footer asks readers to reply, and the From address has no mailbox.<br>**Docs updated:** `docs/EMAIL_SETUP.md`, `config/runtime.env.example` and `deploy/systemd/README.md`. The overnight report is corrected at the top. | `test_cli_send` (the real CLI against a local SMTPS server) |

## 3. End-to-end runs with new candidates (real models, recorded intervention)

Two new candidates were taken through the whole chain on the Pi with the real model (Hermes isolated runner, mimo-v2.6-pro, concurrency 1). The steps were supply, evidence, Chinese draft and review, English, the editor stage (model edits), re-review plus English parity, and admission. **Neither was edited by hand; neither reached inventory.** All numbers come from `validation/chain_stats.py`; the records are in `samples/auto/<candidate>/editor_record.json`.

### Candidate supply

| Attempt | Catalogue entry | Anchors proposed / kept | Result |
|---|---|---|---|
| 1 | SJ068 《史記·商君列傳》 | 25 / 24 | **rejected**: episode years left empty (my prompt said "don't convert to CE years", meant for the article). Prompt fixed. |
| 2 | SJ077 《史記·魏公子列傳》 | 25 / 21 (4 end anchors too short) | candidate `cand-auto-20261030-sj077-1`, 信陵君窃符救赵, dedup distinct |
| 3 | QSG412 《清史稿·左宗棠傳》 | 23 / 21 (1 too short, 1 overlapping) | candidate `cand-auto-20261030-qsg412-1`, 海防/塞防之争, dedup distinct |

Of 73 anchors proposed, 66 passed the exact-match checks. Proposal calls took 3–6 minutes.

### Chain results (two automated attempts, each at most two edit rounds)

| | sj077 (ancient) | qsg412 (modern) |
|---|---|---|
| Pipeline verdict | pending: checker BLOCK + 11 review fix issues | pending: checker BLOCK; **provider refused the review** ("high risk") |
| Length (zh / en) | 9 min / 14 min | 9 min / 12 min |
| Editor attempt 1 (rounds: issues in → edits) | 12 → 24 edits; 5 → 13 edits; **8 open** | 1 → 2; 2 → 4; **3 open** |
| Editor attempt 2 (seeded with the open issues) | 8 → 14; 9 → 17; **3 open** | 3 → 5, then the re-review was **refused again**; 3 open |
| Model time, whole chain | 59.7 min | 31.2 min |
| Outcome | pending (both attempts used) | pending (both attempts used) |

The remaining issues are real:
- **sj077:** "百余乘" (a hundred-odd chariots) comes from a brief line that cited a dropped excerpt. A line of 侯生's is placed in the wrong scene. Staying in Zhao is stated as atonement, but that is a motive.
- **qsg412:** it says the opposing side left "only one sentence", while E3 records their whole argument. A list of reign years skips 四年. An English sentence is truncated.

Almost every edit applied cleanly: across all of today's editor attempts, 160 edits applied and 2 were refused by the exact-match rule. Invalid JSON stayed rare.

### What the runs showed

1. **Convergence, not edit quality, is the limiting factor.** In every round the editor fixed everything it was given; it carried 0 issues over unfixed. But most fresh reviews raised new issues: 0–9 per review, typically 2–3. These were mostly pre-existing problems in other paragraphs, not regressions from the edits. The reviewer samples a few problems per call instead of listing all of them, so a draft with many small latent issues needs more rounds than the bound allows.
2. **Supply flaw found and fixed for future candidates.** When anchors are dropped, the brief lines that cite them gave the drafter facts with no evidence behind them; most of sj077's 11 review issues came from those lines. Such lines are now removed. The two current candidates were not regenerated.
3. **Provider refusals are intermittent on modern-China border topics.** The 左宗棠/新疆 article was refused at the pipeline review, passed both Chinese re-reviews in attempt 1, and was refused again in attempt 2. A refused review leaves the content unreviewed, so it cannot be admitted. Together with the Mao refusals overnight, automated supply for parts of 中国近现代 depends on a second reviewer model or a person.
4. **Cost:** one candidate through the whole chain costs about 30–60 minutes of model time at concurrency 1. Proposal 3–6, pipeline 12–19, editor 11–35.

### Interventions (complete list, from `data/logs/interventions.log`)

| When (CDT) | What | Kind |
|---|---|---|
| 09:55 | Supply attempt 1 rejected (empty years). Clarified the prompt; proposals are now saved. | prompt + code |
| 10:34 | sj077's brief cited dropped excerpts. Brief lines citing dropped excerpts are now removed for **future** candidates. | code |
| 10:35 | qsg412's review was refused. The reason is now named "provider refusal at review_zh" for future runs. Not retried, prompts not reworded. | code |
| 11:02 | A second editor attempt would only have re-reviewed. Attempts are now seeded with the previous attempt's open issues. | code |
| 13:47 | Experiment: a third attempt with 4 rounds on both candidates (section 3a). | run, non-default bound |

No article text, evidence, edit list or record was written by hand during these runs. Code fixes landed between steps, so each report and record carries the code revision it ran under (`code_rev`).

### 3a. Experiment: more rounds (not the default configuration)

To test whether more bounded effort closes the loop, each new candidate got a third attempt with up to 4 rounds (`hip edit --rounds 4`). This is an experiment; the default stays 2 rounds × 2 attempts.

- **sj077:** 4 more rounds and 23 more edits (27.7 min). Open issues went **3 → 4 → 2 → 3 → 5**. Each fresh review found as many new problems as the editor fixed, so it is still pending. Its whole chain cost 86.8 min of model time.
- **qsg412:** the three seeded issues had already been fixed in attempt 2, but that attempt's re-review was refused, so they had stayed open. The editor correctly rejected all three as already fixed, citing the evidence. The fresh review raised 3 new ones. The loop then stopped early: it counted "no edits applied" as no progress, though evidenced rejections are progress. **Fixed, with a test** (`test_evidenced_rejection_counts_as_progress_and_new_issues_get_a_round`). Still pending.

**Conclusion.** With this reviewer and editor (the same model), the chain does not reliably converge, even given twice the rounds. Snow converged because its open issues were few and local. In the drafts with many small problems, every review samples different ones. Two ways forward, both a decision for you (section 6):
- an exhaustive review step: several independent review calls whose issues are pooled, or a different reviewer model
- accepting a person (or Pi Claude as a named editor) as the closing step for drafts left open after the automated attempts

Lowering the fix threshold is not on the list.

## 4. Overnight articles under the new admission rule

The seven articles admitted overnight after Claude's manual editor passes had no review bound to their final content. `hip rereview` ran a fresh Chinese review and English-parity check on each exact text. Under the rule, a draft with any fix-level issue goes back to pending, and **all seven went back to pending.** The nightly-equivalent `hip edit-queue` then gave each one automated editor attempt (two rounds, seeded with those issues).

| Article | Fresh review: open issues | After the automated attempt | Edits | Model min | Status |
|---|---|---|---|---|---|
| 井陉口（jingxing） | 3 | 2 | 9 | 17.2 | pending |
| 华盛顿交还委任状（washington） | 5 | 4 | 20 | 24.1 | pending |
| 沙克尔顿海洋营（shackleton） | 2 | 2 | 5 | 17.1 | pending |
| 斯诺与两家水公司（snow） | 1 | **0** | 2 | 5.9 | **admitted** (`approval: editor-record`) |
| 廉颇蔺相如（lian-lin） | 5 | 5 | 18 | 20.0 | pending |
| 富兰克林 1787（franklin） | 6 | 2 | 17 | 34.4 | pending |
| 达尔文与华莱士（darwin-wallace） | 2 | 2 | 10 | 22.2 | pending |

Several of the fresh issues were introduced by my own manual passes overnight:
- **Washington:** three reservations are listed under the heading "two". The excerpt records only when the letter was read, but the text says it was written that day.
- **Shackleton:** "all figures" is followed by an incomplete list.
- **井陉口:** an evidence id is wrong.

The overnight claim that these seven were "in inventory" was therefore premature under the stricter rule.

## 5. Inventory now

`bin/hip inventory` after all runs (only approved `checked` editions count):

| | china_ancient | world | china_modern | us |
|---|---|---|---|---|
| Schedulable | 0 | 1 (Snow) | 0 | 0 |
| Pending (editor attempts used) | 3 (井陉口, 廉蔺, sj077) | 2 (Shackleton, Darwin–Wallace) | 2 (qsg412, Mao: provider refusal) | 2 (Washington, Franklin) |
| Samples (need `hip approve-sample`) | 1 (A) | 1 (B) | 2 (C, E) | 1 (D) |

**Coverage: 0 days.** The rotation starts with `china_ancient`, which has no schedulable edition. Gaps to 14 days: A 4, W 3, M 3, U 3. The alert is on. 9 drafts are pending, and the catalogue holds 10 entries for future supply.

**Reaching 7 days quickly** (the alert threshold) needs one of these:
- **Approve samples.** If you approve the five samples after reading them, coverage becomes ~~2 days~~ **4 days** (corrected 2026-10-30, STABILIZATION_REVIEW §3): Snow + B give W2, C + E give M2, so A1/W2/M2/U1 fills A, W, M, U, then a second A is missing. (`hip inventory --what-if A=1,W=2,M=2,U=1` → 4.)
- **Close the pending drafts.** A person or a named editor closes the open issues on the pending drafts (2–5 each, all listed in the records). With samples approved, that could give roughly A3/W4/M3/U3: ~~about 10 days~~ **12 days** (corrected; `--what-if A=3,W=4,M=3,U=3` → 12: three full rotations, then a fourth A is missing).

> Correction note: both figures above were hand-computed and wrong. They are now produced by `pipeline.rotation_days()`, the same function `hip inventory` uses (`hip inventory --what-if ...`), with regression tests. They are arithmetic on the counts named, not a claim that samples are approved or that pending drafts will be admitted. Snow has since been returned to pending (legacy record; see docs/FINAL_EDITOR_REPORT.md).
- **Keep supplying.** Supply continues nightly: about 30–90 minutes of model time per candidate, with today's convergence rate of 1 in 9.

## 6. What still needs a person

1. **Decide the closing step for drafts the automated editor cannot finish.** Options:
   - a person
   - Pi Claude as a named, recorded editor
   - a second reviewer model with pooled reviews

   All open issues are listed in each `samples/auto/<id>/editor_record.json`. Admission can then use `hip rereview EDITION --article FILE` after a manual edit; the review is still bound to that exact file. `--exception` is for a reviewer issue you judge wrong, with the reason recorded.
2. **Read and approve samples.** Read at least D or B in both languages, as the review suggests. `hip approve-sample sample-D --reason "..."` makes a sample schedulable.
3. **Modern-China supply.** MiMo refuses some modern topics (Mao; 左宗棠/新疆, intermittently). Either accept a narrower topic range for 中国近现代, or add a second model for those reviews. Prompts are not reworded to get past the filter.
4. **Mail (no code needed).** Set up Resend and `read.starhub.vip`, put the key and an `EMAIL_REPLY_TO` you read into the private file, then run `bin/hip send-test samples/D/article.json --confirm-real-email`. Check both inboxes, spam folders, SPF/DKIM, and that a reply reaches Reply-To. Only then set `EMAIL_SEND_ENABLED=true`.
5. **Website.** Confirm the Cloudflare deploy path. Set `SITE_REPO_PATH`; set `SITE_PUSH_ENABLED=true` only once you approve automatic site commits. A commit made while it was false will be pushed on the next run.
6. **Timers.** Enable only after `hip inventory` shows `coverage_days` ≥ 7 and the steps above are done (`deploy/systemd/README.md`).

## 7. Commands

```bash
bin/hip inventory                         # coverage_days, gaps per category, samples, pending, candidates
bin/hip supply --check                    # fetch status of every catalogue entry
bin/hip supply --category china_modern    # one proposal for one category (logged in data/supply/attempts.jsonl)
bin/hip nightly                           # supply (if < 2 candidates) -> prepare -> edit; never schedules or sends
bin/hip edit EDITION ; bin/hip edit-queue # editor stage
bin/hip rereview EDITION [--article FILE] # fresh bound review of current (or manually edited) content
bin/hip admit ART EV --record REC [--exception "named, human-approved reason"]
bin/hip approve-sample sample-D --reason "read and approved by both readers"
bin/hip send-test samples/D/article.json --confirm-real-email
.venv/bin/python -I validation/chain_stats.py   # per-candidate chain metrics
```

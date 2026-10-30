# Round 3 report: review fixes, Pi-local Claude runtime and the named final editor (2026-10-30)

Responds to `docs/reviews/STABILIZATION_REVIEW.md` (24b34d5) and `docs/CLAUDE_RUNTIME_OPTIONS.md` (c3bc2cc).
Still a draft PR: nothing merged, deployed or emailed; no timer enabled. The owner's sample feedback has not
arrived; no sample is marked as read or approved by the two readers.

## 1. Summary

- **Review fixes are in** (§2): strict schemas for every model step, the three fact arrays counted (297 stored
  findings had been ignored), the send deadline re-checked after every wait, fetch and recipient, and the
  inventory arithmetic computed by one function (4 and 12 days, not 2 and ~10). Snow was returned to pending.
- **Pi-local Claude runtime verified** (§3): official Claude Code CLI 2.1.308 on the Pi, its own claude.ai
  subscription login, isolated and bounded; 10/10 checks including a run from a `systemd-run --user` unit. It does
  not depend on the Windows machine or this VS Code session.
- **Named final editor works** (§4–5): `hip final-edit` (audit → revise → verify, bounded) closed **all 9 pending
  drafts**, including the two trial articles (sj077 ancient, qsg412 modern). 4 needed one attempt, 5 a second
  (continuation) attempt; 73 minutes of editor time in total; 251 issues fixed, 18 rejected with verified quotes, 0 left
  open. No article text was edited by hand and no exception was used.
- **Coverage: 6 days** (A W M U A W), below the 7-day alert line; it stops at the second modern-China slot. One more
  modern-China article gives 10 days (`--what-if A=3,W=3,M=2,U=2`); <!-- MODERN_RESULT -->
- **Bugs found by the real runs and fixed** (§6): a stopped job left `claude -p` running; a resumed reservation skipped
  the duplicate check (the Mao candidate duplicates sample E); a checker false positive on 每万; a catalogue marker
  that never matched (曾國籓).
- **Still yours** (§8): read the final versions, approve samples, decide the evidence-only calibration for well-known
  identifications, and the existing mail/site/timer items.

## 2. Boundary fixes from the review

| Review item | Fix | Regression tests |
|---|---|---|
| **P1** review/parity JSON accepted without schema; `unsupported_claims` / `invented_inner_life` / `quote_mismatches` ignored | New `schemas.py`: review and parity need a typed `issues` list (severity, problem, location types); drafts and edits have required shapes. An invalid reply is a failed model step (logged `schema_problems`, one retry), never a clean review. The three fact arrays become fix-level issues. Admission re-validates the final bound review and **recomputes** its issues instead of trusting the record's `remaining`. Records whose final review predates `review_zh/v2` are legacy and refused. Whole-article `--exception` is refused: one `ISSUE_ID=REASON` per open issue. | `test_schemas.py` (8): `{}`, missing issues, `issues=null`, `issues` a string, unknown severity, issue without problem, fact array not a list; each fact array alone; a hand-made record with an empty or legacy review; a record that hides its review's findings; a clean valid review still admits. Pipeline, editor and hand-made-record paths. |
| **P2** polling could cross the deadline and still send | Backoff sleeps are clamped to the time left; no fetch starts after the deadline; the deadline is re-checked after the last fetch, before email, and before each recipient. Crossing it makes the edition `overdue`. Accepted sends stay recorded; recipients not started are reported `not_started_deadline` and never sent late. | `test_publish.py` (+4): live at exactly 11:00:00 sends; the review's 10:59:30 case (wait clamped to 30 s, oversleep stops, nothing sent); a fetch that returns after the deadline records `site_live` but sends nothing (also on rerun); the deadline passing between two recipients keeps the first `accepted` and sends no second. |
| **§3** report arithmetic | `pipeline.rotation_days()` is now the only coverage calculation; `hip inventory --what-if A=1,W=2,M=2,U=1` → **4** days (report said 2), `A=3,W=4,M=3,U=3` → **12** (report said ~10). Corrected in `STABILIZATION_REPORT.md` §5 with a note. | `test_inventory.Arithmetic` |

**What P1 changed in practice.** The stored model reviews held **297** fact-array findings that had never been
counted (190 unsupported claims, 84 invented inner life, 23 quote mismatches). Every pending draft's final
MiMo review had some. Snow, the one draft admitted in the last round, had one (`analysis.1`: "斯诺选了更费事的路"
presents a choice the evidence does not record); its record is also legacy. **Snow was returned to pending**
(`hip requeue`, reason recorded; database backed up first).

## 3. Pi-local Claude runtime (not the Windows session)

`docs/CLAUDE_RUNTIME_OPTIONS.md` asked not to treat "Pi Claude" as an existing capability. What was checked:

- **Pi**: raspberrypi51, Debian 12 bookworm, aarch64 (64-bit), 7.9 GiB RAM.
- **Before**: no standalone `claude` on the Pi. The interactive development session is the VS Code extension's bundled
  binary (2.1.314), started by the VS Code SSH server on the Pi and logged in through `~/.claude`; it depends on that
  session and was not used for the editor.
- **Installed**: official Claude Code **2.1.308 (stable)** with the native installer (script read first; user-level
  `~/.local/bin/claude`, no sudo, no shell files changed). The release manifest's GPG signature verifies against
  Anthropic's key (fingerprint `31DD DE24 … 1A7E CACE`) and the binary's SHA-256 matches the manifest. Hermes and the
  gateway were not touched.
- **Dedicated config**: `~/.config/history-in-practice/claude` (0700): autoupdater off, built-in plugins disabled.
  The owner logged in to it with `claude auth login` (claude.ai account, Max subscription); the one-time code was
  relayed through the chat at the owner's explicit request and was spent on use.
- **Adapter** `src/history_in_practice/claude_cli.py`: allowlisted environment (never forwards `ANTHROPIC_API_KEY`,
  `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN` or provider switches); `preflight()` refuses unless
  `claude auth status` reports `authMethod: claude.ai`; `--safe-mode --disable-slash-commands --tools ""
  --disallowedTools mcp__* --strict-mcp-config --no-session-persistence`, empty temporary working directory,
  process-group timeout, stdout cap. The CLI's own init event is checked on every call; any tool, MCP server,
  plugin, skill or API-key source and the output is discarded. **`--bare` is not used**: it ignores the
  subscription login and would need an API key.

`validation/claude_runtime_check.py` (report `data/logs/claude_runtime_check-20261030T162209.json`): **10/10 pass**.

| Check | Result |
|---|---|
| install | 2.1.308, signed manifest verified |
| auth | logged in, `authMethod: claude.ai`, subscription `max` |
| guard | a fake `ANTHROPIC_API_KEY` flips the CLI to `api_key`; preflight refuses (no silent API billing) |
| smoke | `-p` call returns `OK`; init shows no tools, no MCP, `apiKeySource: none` |
| canary | a CLAUDE.md with a canary placed in the dedicated config is not loaded (`NONE`) |
| no_tools | asked to run `ls /`: replies `NO_TOOLS`, one turn |
| context | a real evidence pack + article (25k chars): counts 21 excerpts / 23 paragraphs correctly |
| timeout | 3 s timeout kills the process group; no stragglers |
| not_logged | an empty config dir is refused by preflight |
| systemd | the smoke call from a transient `systemd-run --user` unit (the timers' environment; lingering on): OK, no Anthropic/Claude variables in the environment; no timer enabled |

The first run failed closed (5/10): the init event listed two built-in plugins and the bundled skills, so the adapter
discarded every output. Fixed with `--disable-slash-commands` and `enabledPlugins: false` in the dedicated settings;
the check now also requires zero skills and commands. The CLI still lists its built-in agent types, but with no tools
nothing can invoke them.

**Limits that remain.** The access token lasts 8 h and is refreshed by the CLI; the refresh token expires in about
29 days, and whether refreshes extend it is not yet observed. `claude_cli.warnings()` reports it under 7 days; the
owner then re-runs `claude auth login` with the dedicated config. Subscription use is shared with the owner's other
Claude use and is not unlimited; `total_cost_usd` in CLI output is a client-side estimate, not a bill. A rate-limit
or authentication failure leaves the item pending (no retry loop, no fallback to an API key).

## 4. The named final editor (`hip final-edit`, `src/history_in_practice/final_edit.py`)

Per edition, all calls through `claude_cli` (Pi Claude, `claude-opus-5-5`, subscription):

1. **Audit.** The whole article (every field, zh and en, with paragraph kinds and cited evidence ids) and the whole
   evidence pack. For every field: facts, attribution, chronology, causality, quotes, inner life, interpretation
   labels, EN/ZH parity. Every inherited MiMo issue gets a verdict (valid / invalid with a quote / duplicate). Every
   **contamination** line is checked: brief lines citing excerpts that were later dropped (8 in sj077, 3 in qsg412),
   as the review asked ("先移除掉落证据遗留事实"). Strict schema: coverage of every field path, known categories,
   a fact problem can never be a "note".
2. **Revise.** Each fix/block issue: full-field replacement (zh and en together), citation or kind change, or a
   rejection with a verbatim evidence quote. Deterministic checks decide: "fixed" counts only with a change that
   cites the issue; "rejected" only if the quote really occurs in that excerpt (whitespace and 繁简 normalised).
3. **Verify.** A fresh field-by-field pass over the final text, bound to its content hash. Its fix/block findings get
   one more revise/verify round (`final_editor.max_rounds` 2), then stay open.
4. **Continuation.** If issues remain, one more attempt (`max_attempts` 2) starts from the previous final text and its
   open issues, with a full fresh audit. No MiMo rounds were added anywhere.

**Record** (`samples/auto/<cid>/final/final_editor_record.json`; every attempt kept as `attempt-N_…`): editor identity
(name, model reported by the CLI, CLI version, auth method), base / final content hashes, evidence hash, the full edit
log (before/after per field, replayable from `base_article.json`), every issue with origin, disposition, rationale and
evidence, the audit and verify outputs, per-call timings and token use, elapsed minutes.

**Admission** (`final_edit.admit`, also via `hip admit --record`) re-checks all of it: identity, hashes, edit-log replay,
audit and verify coverage, verify bound to the final text, every disposition, inherited issues carried, checker clean.
**No exception path.** The approval string names the editor and the record hash, e.g.
`final-editor: Pi Claude (claude-opus-5-5, Claude Code 2.1.308); record 14496d305f74`.

Tests: `test_final_edit.py` (8) with a scripted model: happy path with replay; a fabricated rejection quote stays open
and a real one closes; "fixed" without a change stays open; persistent verify findings stop after the bounded rounds;
a fact issue as "note" and incomplete coverage fail the schema; tampered text, a forged edit log and an exception are
refused; a second attempt continues from the first; the real CLI is never called without a subscription login.

## 5. Results

### Trial (one ancient, one modern), then the remaining pending drafts

Computed from the records by `validation/final_edit_stats.py` (fix/block issues include MiMo issues judged as duplicates;
"verify fix/block per round" is the number of new fix/block findings in each verify pass, across attempts):

| Edition | Attempts | Minutes | Calls | Out tokens (k) | MiMo issues inherited | Fix/block issues | Fixed / rejected / dup / open | Edits | Verify fix/block per round | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 20261030-darwin-wallace | 1 | 6.8 | 5 | 48.9 | 12 | 33 | 21 / 2 / 10 / 0 | 31 | 1 → 0 | admitted |
| 20261030-franklin-1787 | 2 | 9.2 | 8 | 66.8 | 15 | 50 | 39 / 1 / 7 / 0 | 43 | 2 → 3 → 0 | admitted |
| 20261030-jingxing | 1 | 6.2 | 5 | 43.8 | 7 | 30 | 23 / 0 / 7 / 0 | 26 | 3 → 0 | admitted |
| 20261030-lian-lin | 1 | 6.7 | 5 | 49.0 | 14 | 40 | 33 / 4 / 3 / 0 | 25 | 2 → 0 | admitted |
| 20261030-shackleton-ocean-camp | 2 | 8.3 | 8 | 60.2 | 11 | 33 | 21 / 5 / 6 / 0 | 28 | 3 → 1 → 0 | admitted |
| 20261030-snow-water-companies | 2 | 8.5 | 10 | 60.9 | 1 | 19 | 15 / 0 / 2 / 0 (+1 checker) | 28 | 2 → 1 → 1 → 0 | admitted |
| 20261030-washington-resigns | 2 | 8.1 | 8 | 58.0 | 8 | 31 | 22 / 0 / 8 / 0 | 32 | 5 → 1 → 0 | admitted |
| auto-20261030-qsg412-1 | 1 | 5.9 | 5 | 41.8 | 9 | 32 | 23 / 3 / 6 / 0 | 26 | 1 → 0 | admitted |
| auto-20261030-sj077-1 | 2 | 13.6 | 8 | 97.3 | 14 | 69 | 54 / 3 / 11 / 0 | 54 | 5 → 1 → 0 | admitted |

Totals: 9 editions, 13 attempts (4 × 1, 5 × 2), 62 model calls, 0 retries, 73.3 minutes, about 527k output tokens.
91 inherited MiMo issues all judged; 251 issues fixed, 18 rejected with verified quotes, 60 duplicates, 7 carried
into a continuation attempt (all closed there), 1 closed by a checker correction (Snow, §6), 0 open.

**Trial articles.** qsg412 (左宗棠, modern) was admitted on the first attempt (5.9 min). sj077 (信陵君, ancient) ended
attempt 1 with one open attribution issue (43 → 5 → 1 fix/block findings); the continuation attempt closed it and five
smaller findings of its fresh audit (3.5 min). Both records were then re-verified from scratch, as were all nine.

**What the editor actually caught** (most frequent audit categories across the nine): unsupported specifics (facts 57,
unsupported 27), English quotation marks around translations presented as source text (quotes 27), author judgements
in record paragraphs without a label (22), EN/ZH differences (19), attribution (11), chronology (9). Examples checked by
hand against the evidence: sj077 "不居功" where the source first records 「意驕矜而有自功之色」; qsg412 俄国「代取」乌鲁木齐
rewritten as Russia's own plan; 「願弱」 translated "willing"; Washington's six-clause resolution described as three
clauses and the commission received by the Secretary rather than the President. In each case the final text matches
the cited excerpt.

**Costs to readability (reported, not hidden).** Removing everything the evidence pack does not support has a price.
sj077 never names 信陵君/无忌 (the pack has no excerpt with the name) and repeats "决意赴秦军而死"; qsg412 and Washington
stay close to the source wording in places; English drops widely known identifications the pack does not state
(高宗 = Qianlong, 鸿章 = Li Hongzhang). See §8 for the calibration decision.

### Coverage after the batch

`hip inventory`: schedulable A3 / W3 / M1 / U2; **coverage 6 days** (A W M U A W), stopping at the second modern-China
slot; pending 0; samples 5 (none approved). Gaps to the 14-day target: A 1, W 1, M 2, U 1.

<!-- MODERN_SECTION -->

## 6. Defects the real runs exposed (all fixed, with tests)

| Found | Fix | Test |
|---|---|---|
| Stopping the batch (SIGTERM) left its `claude -p` child running under systemd (own process group); found and killed by hand | The CLI maps SIGTERM to `SystemExit`; both adapters (`claude_cli`, `llm`) kill the child's process group in `finally` | `test_child_cleanup` (fails without the fix and leaves the orphan) |
| The Mao candidate (MiMo provider refusal) was drafted by Claude (no refusal; 4.4 min), then the registry refused to re-activate it: sample E already uses the same 1930 passage. A resumed own reservation had skipped the duplicate check | `prepare()` re-checks the core span of a resumed rejected reservation before any model call; Mao rejected as a duplicate of sample E | `test_resumed_rejected_reservation…` |
| Snow's last open issue was a checker false positive: 每万户 vs "per 10,000" | Checker parses 每百/每千/每万; at admission an open checker-origin issue counts as closed only if the current checker no longer reports it on that exact content | `test_per_ten_thousand…` |
| Supply rejected QSG405 in one second as "extractable": the catalogue marker 曾國藩 never matches Wikisource's 曾國籓 | Marker corrected; stale cache entry moved to `data/backup/` | `hip supply --check` now 10/10 `evidence_usable` |

Interventions (all code, config or process, none on article text) are logged in `docs/stabilization_interventions.log`.

## 7. What was not done (by instruction)

No merge, no deploy, no real email, no production timer. The two readers have not reported on the samples; no sample is
marked approved or read. `hip approve-sample` remains the owner's step. The `hip nightly` timer template still runs the
MiMo editor stage and not the final editor; wiring the final editor into an unattended timer waits for the decisions in §8.

## 8. Decisions for the owner

1. **Read the final versions** (links in `samples/README.md`, `auto/<cid>/final/article.zh.md`). The records show
   what changed and why; the model editor is not a guarantee of zero historical error, and sources stay linked for
   corrections.
2. **Evidence-only calibration.** Today a widely known identification that the evidence pack does not state (a temple
   name's emperor, a full personal name, a place gloss) is removed. Options: keep the strict rule; or allow a small
   reference layer (e.g. a second excerpt from the same work naming the person, or a curated glossary with its own
   source) that the editor may cite. The second keeps the standard and improves English readability.
3. **Samples.** Approve the ones you are happy with (`hip approve-sample EDITION --reason "..."`). Arithmetic only (same
   `rotation_days()`): with all five approved (A, B, C, D, E → +1 A, +1 W, +2 M, +1 U) the counts become A4/W4/M3/U3,
   which is **14 days** (`hip inventory --what-if A=4,W=4,M=3,U=3`). This is not a claim that they will be approved;
   the samples have not had a final-editor pass, so reading them is also the content check.
4. **Unattended final editor.** If you want the nightly job to call the final editor, it would run at most
   `max_attempts` per draft, leave failures pending, and alert on login expiry (`claude_cli.warnings()`); subscription
   use is shared with your own Claude use.
5. Unchanged from before: Resend and Reply-To, the `send-test` email check, the Cloudflare deploy path, timers only
   after at least 7 days of coverage.


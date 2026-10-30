# Overnight report — 2026-10-30 (Pi, Claude Opus)

> **Corrections after review (2026-10-30, see `docs/reviews/POST_OVERNIGHT_REVIEW.md` and `docs/STABILIZATION_REPORT.md`):** the "12 days" below was 12 *articles*; under the A→W→M→U rotation they covered only 10 consecutive days, and under the stricter admission rules introduced afterwards none of them is schedulable until re-reviewed or (for samples) approved. Step 7.6 below could not work as written (`hip send --real` refuses while `EMAIL_SEND_ENABLED=false`), and Reply-To is required, not optional. The corrected steps are in `docs/EMAIL_SETUP.md` and the stabilisation report.

Branch `impl/overnight-20261030`, mirrored to the PR #1 branch `review/fable-2026-10-30`. Nothing was merged, deployed, scheduled or emailed.

## 1. Summary

**Samples.** Five bilingual samples, each sized for reading in one language, not for the two languages together:

- A–D are Hermes-drafted and editor-corrected.
- E (Mao, 1930/1941) was written by Claude from its evidence pack, because the model provider refused the topic. It is labelled as such.
- All five have no BLOCK or FIX findings.
- Chinese runs about 8 min (2,534–2,673 characters, not padded). English runs 9–13 min.

Entry points: `samples/README.md`, plus email and site previews (§2).

**Automated supply.** Eight real candidates went through the pipeline (`hip prepare-queue`): source fetch → anchored evidence → admission → dedup registry → Hermes ×3 → checks.

- **Seven** articles are now in inventory after a logged editor pass and `hip admit --from-pending`.
- **One** (Mao) is pending: the provider refused it, and it was not retried or reworded.
- Inventory was **12 articles** (counting the five samples): china_ancient 3, china_modern 2, us 3, world 4. *(Correction: that is 10 consecutive days under the rotation, not 12; see the note at the top.)* The target is 14.

**The main finding: no automated draft was publishable as it came out.**

- Under the current rule, every draft would have gone to `pending_review`.
- The model's own review found 3–13 fix-level issues per draft. Typical ones:
  - specifics outside the evidence: years, ship names, place names, page counts
  - motives written as fact
  - truncated quotations that changed the meaning
  - speakers out of order
  - modern scenes that repeat the open question
- The editor passes are logged edit by edit in `samples/auto/<candidate>/editor_log.json`.

**Length depends on the evidence pack.** The first automated drafts had 8–10 excerpts each and came out at 6–7 minutes in Chinese. After widening the excerpts from the same cached sources (17–24 per candidate), drafts and edited articles run 9–10 minutes in Chinese and 11–12 in English, without padding.

**Code.**

- Python package with the full `bin/hip` CLI and SQLite state with crash recovery.
- Per-recipient SMTP sending, tested only against a local SMTPS server.
- Site export with live verification, and a resumable `publish-today`.
- **46 `unittest` cases, passing on a fresh clone.**

**Bugs found tonight by running for real, all fixed and tested (§4):**

- crash on list-valued model fields
- orphaned registry reservation after a crash
- a rule that let substantive review issues through
- reruns overwriting model metrics
- `publish-today` skipping an in-flight edition
- `hip render` crashing on unscheduled inventory
- the call log missing `json_ok`
- `.gitignore` hiding the site preview data
- tests depending on git-ignored data

Two of these were lessons rather than code bugs:

- **Long-running queue processes keep the code they started with.** Queue 2 judged two candidates under the old rule. Reports now record `code_rev`.
- **A shell waiter that `pgrep`s its own command never returns.** Queue 3 had to be started by hand.

**Not done (by instruction or blocked on accounts):** real email, Cloudflare/website deployment, systemd timers, merge. What to set up this morning is in §7.

## 2. Samples, automated articles and previews

Everything below is generated from the files by `validation/samples_readme.py` (see `samples/README.md` for the full tables). Reading time is an estimate at 320 Chinese characters and 200 English words per minute, counting body, open question and example, but not sources.

### Samples (`status: sample`)

| Sample | Chinese | English | Evidence | How made |
|---|---|---|---|---|
| A 中国古代 · 韩信、陈平、范增：项羽留不住的三个人 | 2,673 字 · ~8 min | 2,682 words · ~13 min | 20 excerpts, one basis (Shiji), disclosed | Hermes ×3, 16 editor changes |
| B 世界史 · 拆掉水泵把手，宽街的霍乱就停了吗？ | 2,668 字 · ~8 min | 2,272 words · ~11 min | 20 excerpts | Hermes ×3, 23 editor changes |
| C 中国近现代 · 快要毕业时，一百个留学生被叫回国 | 2,534 字 · ~8 min | 2,192 words · ~11 min | 23 excerpts | Hermes ×3, 17 editor changes |
| D 美国史 · 欠饷是真的，匿名信也是真的：华盛顿在纽堡站在哪里 | 2,554 字 · ~8 min | 2,002 words · ~10 min | 17 excerpts | Hermes ×3, 14 editor changes |
| E 中国近现代 · 没有调查，没有发言权：这句话原本要求什么 | 2,605 字 · ~8 min | 1,898 words · ~9 min | 24 excerpts | **written by Claude** after the provider refused (marked in the file and README) |

- **Chinese runs short of the 2,800-character reference.** It was not padded; calibrate with the two readers' real times first.
- **A's English is long (~13 min).** Its English-only tightening call stalled (§5).

### Automated articles in inventory (unscheduled)

| Candidate | Chinese | English | Excerpts | Pipeline verdict | Editor pass |
|---|---|---|---|---|---|
| 井陉口前，那条没人听的计 (china_ancient) | ~9 min | ~12 min | 10 | pending_review (checker BLOCK) | 30 edits |
| 鞠躬的人与脱帽的人：1783年的一次权力交还 (us) | ~9 min | ~12 min | 9 → 18 | pending_review (BLOCK, 6 fix) | 33 edits, two passes |
| 走六英里，进一英里 — Shackleton, Ocean Camp (world) | ~9 min | ~11 min | 8 → 18 | `checked` by pre-rule code; would be pending | 39 edits, two passes |
| 同一条街上的两根水管 — Snow, water companies (world) | ~9 min | ~11 min | 8 → 12 | `checked` by pre-rule code (13 fix issues); requeued | 14 edits incl. section rewrites |
| 位次之争：廉颇的委屈与那根荆条 (china_ancient) | ~9 min | ~12 min | 17 | pending_review (BLOCK, 5 fix) | 34 edits |
| 看不出是升是落 — Franklin, 17 Sept 1787 (us) | ~10 min | ~11 min | 24 | pending_review (8 BLOCK, 3 fix) | 12 edits incl. section rewrites |
| 同一个想法，两份手稿 — Darwin and Wallace, 1858 (world) | ~8 min | ~9 min | 22 | pending_review (BLOCK, 6 fix, 1 FIX) | 10 edits incl. section rewrites (inline evidence IDs removed from the prose) |
| Mao, 调查 (china_modern) | — | — | 24 | **pending**: provider refusal, 2 calls × ~6 s | not edited (same texts covered by sample E) |

Each article directory `samples/auto/<candidate>/` holds:

- `article.json`, `article.zh.md` and `article.en.md`
- `evidence.json`
- the model's raw outputs (`model_*.json`)
- `edits.json` and `editor_log.json`, recording before, after and the reason for every change

### Previews

| Preview | Location |
|---|---|
| Email | `samples/preview/email/<id>.html`, `.txt`, `.reader1.eml` / `.reader2.eml` (fictional `example.invalid` recipients); samples A–E and every automated article |
| Site | `samples/preview/site/`. Serve with `python3 -I validation/preview_server.py 18767 samples/preview/site`, then open `http://127.0.0.1:18767/history/`. Samples are listed; unscheduled inventory is in `data/history/unscheduled/` and deliberately not in the public index. |
| Screenshots | `samples/preview/screenshots/` (desktop and mobile, zh and en, list, two error states, StarHub nav entry) |
| GitHub-readable | `samples/X/article.{zh,en}.md`, `samples/auto/<candidate>/article.{zh,en}.md` |

## 3. Code

`src/history_in_practice/` (stdlib + `opencc-python-reimplemented`), CLI `bin/hip`:

| Module | Responsibility | Status |
|---|---|---|
| `sources` | Fetch per adapter (`wikisource_render`, `archive_djvu`, `html`), classify `evidence_usable / extractable / challenge_page / wrong_url / site_fallback / http_error`, cache text + SHA-256 | real (every sample and candidate) + local tests |
| `evidence` | Verbatim excerpts cut by start/end anchors, with offset and source hash; canonical spans for the registry | real + tests |
| `registry` | Immutable episode IDs, `parent_event`, alias / 繁简 / QID-redirect normalisation, source-span overlap, CJK bigram FTS + `instr`, active-status coverage, unique core span, rebuild from content | real (13 episodes registered: 12 checked, Mao released after refusal) + tests (13 dedup cases) |
| `llm` + `hermes_isolated` | Project-level isolated Hermes call (0 tools, no SOUL/memory/AGENTS), prompt on stdin, process-group timeout, live output cap | real (all model calls) + tests with a fake runner |
| `checks` | Evidence IDs, classical quotes (繁简) and English quotes (verbatim) against cited excerpts, English numbers absent from Chinese = BLOCK, modern scene repeating the open question = FIX | real + tests |
| `render` | One object → email HTML/text/.eml, site JSON + index, GitHub Markdown; `content_sha256` over both languages, Q&A and sources; unscheduled inventory gets email + preview JSON but never the public index | real + tests |
| `state` | SQLite edition state machine, frozen content, per-recipient deliveries keyed by salted hash, `recover()` turns `sending` into `unknown` | real (inventory) + tests |
| `mailer` | One SMTP sender (SMTPS/STARTTLS), per-recipient `accepted / failed / unknown`, stable Message-ID, send gate | local (SMTPS fixture) |
| `site_export` | Allow-listed export (`history/`, `data/history/`), live check by JSON + revision + recomputed hash + both languages | local fixtures; real site pending |
| `publish` | Schedule by rotation → archive to `content/` → commit website copy → verify live → email; resumes in-flight editions | local end-to-end test |
| `pipeline` | candidate → fetch → evidence → admission → registry → Hermes ×3 → assemble → checks → inventory or pending. Resumes from saved step outputs; append-only `calls.jsonl` written after parsing; provider refusal → pending without retry; review severity `fix`/`block` → pending; report records `code_rev` | real (8 candidates) + mock tests |
| `cli` | `doctor --probe`, `prepare`, `prepare-queue`, `check`, `render`, `export-site`, `verify-site`, `send`, `retry-send`, `publish-today`, `status`, `inventory`, `recover`, `requeue`, `admit [--from-pending]`, `registry-rebuild` | real for doctor, prepare-queue, render, requeue, admit, status, inventory; others local |

**Editor tooling** (`validation/`):

- `editor_pass.py` applies logged edits to a draft and re-checks it. Edits can be find/replace, a field value, or a whole section's paragraph list.
- `samples_readme.py` generates the README tables.
- `overnight_stats.py` computes the model statistics.

**Website.** `deploy/website_test/0001-*.patch` adds `history/`, `data/history/` and one nav link. That is a one-line change in `index.html`, with the original line endings kept.

- It is committed on a local branch in `data/website_test`, which is git-ignored.
- **Not pushed:** a pushed branch could trigger a Cloudflare preview build, and the deploy command is unverified.

**systemd.** `deploy/systemd/hip-{prepare,send}.{service,timer}` are templates:

- Los Angeles time zone and a batch budget for preparation.
- `LimitAS`, because the user cgroup ignores `MemoryMax`.
- **Not installed, not enabled.**

## 4. Verification

Legend:

- **real**: ran on the Pi against the real Hermes model, real network fetches and real files.
- **local**: simulated locally with fixtures (local SMTPS server, fake site).
- **pending config**: blocked on an outside account or permission.

| What | How | Result | Class |
|---|---|---|---|
| Hermes isolation | `hip doctor --probe`: real Hermes entry point, `chat` replaced, no model call | 0 tools, no SOUL, no memory, no cwd AGENTS canary | real |
| Hermes calls | 54 calls through the isolated runner (samples and 8 candidates) | see §5 | real |
| Runner bounds | fake runner: valid, error exit, empty output, hang with a grandchild, 5 MB flood | timeout kills the whole process group; output cap stops the flood while running | local |
| Sources | 31 documents for the samples, plus the candidates' sources, fetched and classified per document | challenge pages (ctext, Founders), 403 (loc.gov), 404, site fallback (starhub), reachable-but-irrelevant all detected | real + local |
| Evidence | 104 excerpts for the samples and 145 for the candidates, all cut by anchors in cached text | every quote is an exact span; every new anchor tonight was checked to occur exactly once; missing anchors are refused | real + local |
| Automated supply | `hip prepare-queue` on 8 real candidates | every non-refused draft ended in pending_review under the current rule (two only after `requeue`, because queue 2 ran pre-rule code) → editor pass → `admit --from-pending`; 1 refusal → pending; resumed after a crash without re-calling the model | real |
| Dedup | retitle, English names, 繁体, aliases only, other category, QID redirect, missing QID, prepared-not-published duplicate, racing insert, same parent event / different episode, same person-year-place / different decision, other-work paraphrase → review, rebuild from content | all pass | local |
| Checks | missing / unknown evidence id, invented quote, modern Chinese in 「」, English number absent from Chinese, modern scene citing evidence, today-scene repeating the question | BLOCK/FIX as designed; the checker itself flagged 6 of the 7 drafts (BLOCK or FIX); the model review flagged all 7 | real + local |
| Pipeline rules | mock model: good → inventory; missing source → pending, others continue; duplicate → rejected; timeout → pending without a second full timeout; refusal → pending without retry; review `fix` → pending; call log records `json_ok` / refusal | all pass | local |
| Publish flow | temp content dir + temp website git repo + live check + local SMTPS | archive → resume without rewriting; only allow-listed files committed; one recipient refused → partial → retry sends only that one; stale live copy blocks email; empty rotation slot → skip | local |
| Site verification | 200 homepage fallback, old revision, same id/title with changed body (hash), missing English | all rejected | local |
| SMTP | `hip send --local-smtp` against local SMTPS with 3 fictional recipients | run 1: accepted / failed (RCPT 550) / unknown (drop during DATA); run 2: only the failed one resent; exit 3 while any is not accepted | local (`data/logs/local_smtp_demo.txt`) |
| Email size | rendered long articles | HTML 34–41 KB, text 24–31 KB (budget 90 KB) | real render; **real client display not tested** |
| Site page | headless Firefox screenshots; preview served from a fresh clone | renders; fallback and missing story show an error banner | local |
| Fresh clone | `git clone` + test suite + preview server | 46 tests pass; preview index and article JSON served (200) | local |
| Private data | grep of the repo, previews and tests for both real addresses | not present; addresses only in `~/.config/history-in-practice/runtime.env` (0600) | real |
| Real email delivery | — | not attempted (no Resend account/key; sending disabled) | pending config |
| Cloudflare deployment | — | not attempted; website change kept as a local patch | pending config |

## 5. Model timings

Computed from saved call records by `validation/overnight_stats.py`: the sample stages come from `samples/model_timings*.json`, the candidates from `data/drafts/*/calls.jsonl`. Rerun the script to refresh.

| Group | Calls, time, failures |
|---|---|
| stage 1 (short samples) | 12 calls, 2203 s total, longest 362 s, invalid/no JSON 0 (refusals 0, killed/stopped 0) |
| stage 2 (ten-minute expansion) | 14 calls, 2671 s total, longest 254 s, invalid/no JSON 3 (refusals 0, killed/stopped 0) |
| stage 3 (English tightening) | 1 calls, 1139 s total, longest 1139 s, invalid/no JSON 1 (refusals 0, killed/stopped 1) |
| automated candidates | 27 calls, 5530 s total, longest 360 s, invalid/no JSON 6 (refusals 2, killed/stopped 0) |
| ALL | 54 model calls, 192.4 min of model time |

Per automated candidate:

| Candidate | Calls | Model time | Steps (wall s) | Invalid JSON | Refusals |
|---|---|---|---|---|---|
| darwin-wallace | 4 | 13.5 min | draft_zh 186 · review_zh 232 · en 190 · en 203 | 1 | 0 |
| franklin-1787 | 3 | 16.9 min | draft_zh 333 · review_zh 324 · en 360 | 0 | 0 |
| jingxing | 4 | 15.6 min | draft_zh 270 · draft_zh 245 · review_zh 184 · en 237 | 1 | 0 |
| lian-lin | 4 | 13.7 min | draft_zh 203 · draft_zh 280 · review_zh 167 · en 170 | 1 | 0 |
| mao-diaocha | 2 | 0.2 min | draft_zh 6 · draft_zh 7 | 0 | 2 |
| shackleton-ocean-camp | 3 | 10.5 min | draft_zh 253 · review_zh 197 · en 181 | 0 | 0 |
| snow-water-companies | 4 | 13.5 min | draft_zh 305 · draft_zh 208 · review_zh 135 · en 161 | 1 | 0 |
| washington-resigns | 3 | 8.2 min | draft_zh 233 · review_zh 132 · en 127 | 0 | 0 |

Observations:

- **A normal call takes 2–6 minutes.**
  - Chinese drafting takes 3.5–5.5 minutes, and longer with bigger evidence packs (Franklin's 25 KB prompt: 5.5 min).
  - Review takes 2–5.5 minutes, English 2–6.
  - One automated article is about 8–17 minutes of model time, so at concurrency 1 the model alone allows about 4 articles an hour.
  - The editor pass is the larger cost.
- **Invalid JSON is the main waste.** It hit 4 of 25 non-refused automated calls and 4 of 27 sample calls. One retry fixed every case, at the cost of a full extra call.
- **One stall.** Sample A's English-tightening call ran 19 minutes with no output and was stopped. A 10-minute limit for English-only calls would have saved most of that.
- **Provider refusals are instant.**
  - MiMo rejected both Mao drafting calls in about 6 seconds ("rejected because it was considered high risk").
  - The pipeline now records this as a refusal and moves the candidate to pending without retrying.
  - The prompts were not reworded to get around the filter.

## 6. Recovery and run commands

```bash
cd /home/star/history-in-practice
git fetch && git checkout impl/overnight-20261030       # same commits as PR #1 branch review/fable-2026-10-30
.venv/bin/python -m unittest discover -s tests          # 46 tests
bin/hip doctor --probe                                  # env, isolation probe, private config (set/unset only)
bin/hip status ; bin/hip inventory                      # editions, deliveries, inventory
bin/hip recover                                         # interrupted sends -> unknown (never auto-resent)
bin/hip prepare-queue --max-articles 2                  # new candidates in config/candidates/*.json
bin/hip requeue EDITION --reason "..."                  # checked -> pending (e.g. after a stricter rule)
python3 -I validation/editor_pass.py data/drafts/<cid> samples/auto/<edits>.json   # logged editor pass + checks
bin/hip admit samples/auto/<cid>/article.json samples/auto/<cid>/evidence.json --from-pending
bin/hip render samples/[A-E]/article.json samples/auto/cand-*/article.json --out samples/preview
python3 -I validation/preview_server.py 18767 samples/preview/site   # port 8765 is taken on this Pi
.venv/bin/python -I validation/overnight_stats.py       # model statistics
```

**If a job died mid-run, rerun the same command.**

- **What is already saved:**
  - Fetched sources are cached in `data/source_cache`.
  - Each model step's output is saved in `data/drafts/<cid>/` and reused, never re-called.
  - The episode registry and edition states are in `data/hip.sqlite`.
- **Publishing:** `publish-today` resumes from the last recorded step without regenerating or re-archiving.
- **Interrupted sends:** a delivery left in `sending` becomes `unknown` and is reported, not resent. Resend only after checking the recipient's inbox, using `retry-send`, which only touches `failed`.
- **Queue runs:** start a new `prepare-queue` after any code change. A running queue keeps its old code, and each report shows the `code_rev` it was judged with. Do not wait on a queue with `pgrep -f prepare-queue`, because that pattern matches the waiting shell itself.

**After losing SQLite**, rebuild the registry from committed content:

```bash
bin/hip registry-rebuild content/**/*.json samples/*/article.json samples/auto/cand-*/article.json
```

**Manual data fixes** tonight are logged in `data/logs/manual_fixes.log`. There was one: the Mao record's reason text was corrected.

## 7. Must configure this morning

1. **Resend:**
   - Create the account and add the sending subdomain `read.starhub.vip`.
   - Add exactly the DNS records Resend returns in Cloudflare DNS. Do not touch the root domain's existing mail or web records.
   - Wait for verification.
2. **Sending key:**
   - Create a key limited to sending, and to that domain if offered.
   - Put it only in `~/.config/history-in-practice/runtime.env` as `SMTP_PASSWORD=`. The file stays mode 600.
   - Keep `EMAIL_SEND_ENABLED=false` until a manual test send.
3. **Reply-To (required, corrected):** set `EMAIL_REPLY_TO=` to an address you read. The footer asks readers to reply, and the From address has no mailbox; real sending now refuses without it.
4. **Recipients:** already in the private file (2 addresses). Nothing to add unless they change.
5. **Website:**
   - Confirm how starhub.vip deploys: Cloudflare Workers or Pages, production branch, build command.
   - Then decide whether to push `deploy/website_test/0001-*.patch` as a website PR.
   - Set `SITE_REPO_PATH` (a clean working copy) in the private file. Leave `SITE_PUSH_ENABLED` unset until you approve automatic site commits.
6. **First real test (corrected):** only after steps 1–3, run `bin/hip send-test samples/D/article.json --confirm-real-email`. It works while `EMAIL_SEND_ENABLED=false` and uses a separate test edition. Then check both inboxes (Gmail and QQ), spam folders, SPF/DKIM, the layout in each language, and reply once to confirm the Reply-To path. *(The original step, `hip send --real`, refuses while the flag is false.)*
7. **Timers:** only after the above, follow `deploy/systemd/README.md`.

## 8. Not done / open issues

1. **No real email, no deployment, no timers, no merge.** This was by instruction. Resend, the DNS records and the key come first (§7).
2. **Every automated draft needs an editor pass.**
   - The gates work: they caught every draft. But passing the gates after an edit is not the same as being right.
   - The errors tonight were mostly plausible specifics the evidence did not contain, sometimes ones the editor brief itself introduced (dates, ship names).
   - Until reader feedback says otherwise, plan on a human or Claude editor pass before scheduling. The alternative is to accept a lower bar knowingly.
3. **Candidate evidence packs need about 15–25 excerpts** for a ten-minute piece. Write anchors before running the model; it is cheaper than rewriting afterwards.
4. **Inventory was 12 articles, which is 10 days of rotation coverage** (corrected), counting the five samples, which are `status: sample`. Without the samples it was 7 articles.
5. **Chinese samples A–E are about 8 minutes**, under the 2,800-character reference. They were deliberately not padded; calibrate with real readers first. The automated articles are 9–10 minutes.
6. **Sample A's English is about 13 minutes.** The tightening call stalled. Rerun `python3 -I validation/tighten_en.py A`, or trim by hand.
7. **Hermes behaviour:**
   - Occasional invalid JSON (retry fixes it), one 19-minute stall, and refusals of Mao-related prompts.
   - Keep per-call timeouts of 20–30 minutes; consider 10 minutes for English-only calls.
8. **The isolated runner depends on Hermes internals** (the `AIAgent` constructor arguments). Rerun `bin/hip doctor --probe` after any Hermes upgrade.
9. **Production news-intel still calls `hermes -z … -t "" --ignore-rules`**, which enables 29 tools with auto-approval. That is outside this project and was not changed. It is your decision.
10. **The website change is a local patch**, not a PR on `website_test` (see §3).
11. **Translation mapping for dedup.** Spans are compared within the one configured edition of each work, so a translation must be mapped to the original work's reference before it can be compared. Same-episode retellings from a different work, without a QID, only reach `review`.
12. **Log rotation** is a size warning in `hip doctor`, not automatic rotation.
13. **Real email-client rendering** (Gmail, QQ Mail, Apple Mail) is untested. Only the HTML size and structure are verified.
14. **Revision numbers for unpublished edits.** Shackleton and Washington were edited twice while still unpublished; both stay revision 1 with a new `content_sha256`. The state machine only requires a new revision after freezing, which happens at scheduling.

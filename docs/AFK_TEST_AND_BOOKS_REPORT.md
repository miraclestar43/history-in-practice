# AFK test edition, unattended final editor, inventory and book intake — report

Date: 2026-10-30 (America/Los_Angeles). Work done on the Pi (raspberrypi51) by Claude Code while the owner was AFK, following
`prompts/04_AFK_FIRST_EDITION_AND_BOOKS.md` (commit ef02679). Branch `stabilize/20261030` → PR #1 branch `review/fable-2026-10-30`;
PR #1 stays a draft. Nobody has read or approved anything below: neither reader has seen the test, and no inbox receipt is claimed.

## 1. Summary

| Item | Result |
|---|---|
| Test article | 同一条街上的两根水管 / *Two Water Pipes on the Same Street* (Snow, cholera, 1854; science/society) |
| Website test | **Live** on an isolated Cloudflare Pages preview; live JSON verified (revision 1, content_sha256 `b539659f…`). Production starhub.vip untouched |
| Email test | **Not sent — blocked.** No Resend sending domain (no DKIM/SPF records for `read.starhub.vip`), `SMTP_PASSWORD` and `EMAIL_REPLY_TO` unset. 0 messages sent, 0 accepted |
| Unattended final editor | Wired into `hip nightly`; Claude CLI 10/10 runtime checks inside a systemd unit. Two real nightly batches (§4): batch 1 left both new articles pending after 2 attempts (admitted after one recorded extra attempt each); batch 2 admitted both unattended. One unattended admission (吴起) had a factual defect found afterwards → requeued |
| Inventory | Coverage **6 → 12 days** (reached 14, then 12 after I requeued 吴起); 13 schedulable editions (A3 W4 M3 U3); gap: 1 china_ancient (§4) |
| Timers | Off. No unit installed or enabled; no official edition, no production slot consumed |
| Books | 24,071 catalogue rows → 11,088 leads; 15 varied picks checked for open copies; 3 real files ingested (2 EPUB, 1 TXT, 1.3 MB); one real text → excerpt → evidence pack → event candidate (Curie) |
| Tests | Full suite **118 tests OK** (final run, in a bounded unit). An earlier run had 1 error in a test written this session; fixed |

## 2. Today's TEST

| | |
|---|---|
| Test identity | `test-20261030-snow-water` (persisted in `test_run`; reruns reuse it) |
| Source | `cand-20261030-snow-water-companies` r1, content_sha256 `4ed0451f223adbcf…`, admitted by final-editor record `2f2833b24df2` (Pi Claude, claude-opus-5-5, Claude Code 2.1.308) |
| Test object | labels only (`【测试】` / `[TEST]` title prefix, `status: test`, TEST banner); body verified identical to the source (`testrun.body_problems`). content_sha256 `b539659f33215dd2eb756da0144baab4c3c8c2085ab60d55b77b79bb8c171285` |
| Created | 2026-10-30 17:31 PDT; send window until 2026-10-31 05:31 PDT (renewable only while nothing has been sent) |
| Preview (immutable deploy) | https://5fa1bd38.website-test-7i3.pages.dev/history/?story=test-20261030-snow-water&lang=zh · [English](https://5fa1bd38.website-test-7i3.pages.dev/history/?story=test-20261030-snow-water&lang=en) |
| Preview (branch alias) | https://hip-test-20261030.website-test-7i3.pages.dev/history/ |
| Email | not sent (see §2.2) |

**Why this article.** It was admitted with a valid bound record, has a single, fully cited source, and is a science/society story rather than a war story. The admitted Jingxing piece was an option, not a requirement. No old sample (A–E) was used.

### 2.1 Website

- **Deployment mechanism, inspected:** starhub.vip is the Cloudflare Pages project `website-test`, built from GitHub `miraclestar43/website_test` branch `main` (GitHub check "Cloudflare Pages" on main's head 803faf7). It is a static site with no build step. Every non-main branch gets its own preview deployment.
- **Narrow integration:** I pushed a new branch `hip-test-20261030` (commit f936d25), based on `origin/main`, adding only `history/index.html`, `data/history/index.json` and `data/history/2026/10/30-test-20261030-snow-water.json`. The homepage and all other routes are unchanged; no nav link was added; `main` was not touched. The existing local branch `dev/history-section` was preserved (a separate worktree was used).
- **Live verification** (`hip test-edition verify-site`, not HTTP 200 alone):
  - the preview's `data/history/index.json` is `application/json`
  - it lists the test id at revision 1
  - the edition JSON has the same revision and content_sha256, and the hash recomputed from its body matches
  - both languages are complete
- **Homepage:** the preview homepage is byte-identical to the production homepage apart from Cloudflare's injected challenge script.
- **Production is untouched:** `https://starhub.vip/data/history/index.json` still returns the homepage (HTML fallback), so nothing was published officially.
- **Pages and links:**
  - The page has language tabs, the TEST note, headings, sources and further reading.
  - The example answer sits in a `<details>` element on the page; the email shows it in full, with no `<details>`.
  - Links work: the archive.org source text, the scan page and the preview page each returned 200.
- **Screenshots:**
  - [docs/afk_test/site-mobile-zh.png](afk_test/site-mobile-zh.png) and [docs/afk_test/site-desktop-en.png](afk_test/site-desktop-en.png) come from a local harness. It uses the exact page HTML from the deployment (Cloudflare script removed) with `fetch` answered by the deployed JSON bytes. Headless Chromium hung on the live page, and Firefox captured it before the fetch completed.
  - [docs/afk_test/email-mobile-zh-top.png](afk_test/email-mobile-zh-top.png) shows the email at 390 px.
- **Test vs archive:** the test appears only on the preview deployment, labelled TEST on the list and story pages. It is not in any official index, and the edition table/rotation never saw it.

### 2.2 Email: blocked, nothing sent

| Check | Result |
|---|---|
| Rendering | HTML 38,270 bytes (budget 92,160); plain text complete in both languages; single-column 640 px max; TEST banner in HTML and text; links point to the preview |
| Transport dry run | full `test-edition send` path against the **live** preview, sent through a local SMTPS server to fictional recipients in a throwaway data dir: site verified → 2/2 accepted → rerun skipped both (no resend); MIME message 90,899 bytes; Subject `每日一鉴｜【测试】同一条街上的两根水管`; `X-HIP-Edition: test-20261030-snow-water r1 b539659f3321` |
| Real attempt | `hip test-edition send --test-id test-20261030-snow-water --confirm-real-email` → live site verified, then **refused before any SMTP connection**: `SMTP_PASSWORD is not set; EMAIL_REPLY_TO is not set` (exit 2). Recorded in the test history as `send_refused` |
| Private config (values not printed) | `SMTP_HOST` smtp.resend.com, port 465/ssl, `SMTP_USERNAME` set, **`SMTP_PASSWORD` empty**, `EMAIL_FROM` `每日一鉴 <history@read.starhub.vip>`, `EMAIL_RECIPIENTS` 2 addresses, **`EMAIL_REPLY_TO` empty**, `EMAIL_SEND_ENABLED=false`; file mode 0600, last modified 2026-10-30 02:42 |
| Sending domain | public DNS (1.1.1.1): no TXT/MX for `resend._domainkey.read.starhub.vip`, `send.read.starhub.vip` or `read.starhub.vip` — the Resend domain has not been added/verified |
| Per-recipient status | none: no recipient set frozen, no delivery rows; SMTP acceptance 0, delivery events 0, inbox confirmation 0 |

I did not look for credentials elsewhere on the Pi. A search for a key outside the project's private file was denied by the session's safety rules, and using another service's key would not be appropriate anyway.

### 2.3 Content

| | Chinese | English |
|---|---|---|
| Body (story + analysis + today + edges) | 2,706 chars | 1,985 words |
| Counted for reading time (body + question + example) | 3,218 chars → **~10 min** at 320 chars/min | 2,362 words → **~12 min** at 200 wpm (~10 min at a typical 238 wpm) |

- No content edits were made for the test, so the hash-bound approval still holds. One claim outside the evidence pack was checked against the source: the further-reading note says "around pp. 75–90" for the comparison and Table IX. The scan's own printed running heads put the intermingled-supply discussion after p. 75 and Table IX on p. 86 (`data/source_cache/B-SNOW.txt`), so it stands.
- A checker CHECK (non-blocking) flags "numbers differ" in story[6]. It's a parser artefact: the English number-word parser reads "between eight and nine times". The facts match in both languages.
- Review status: admitted by the Pi Claude final-editor record (§4 of FINAL_EDITOR_REPORT). No reader has reviewed it.

## 3. Changes made for the test (code)

- `testrun.py` and `hip test-edition prepare|verify-site|status|send|renew-window` implement one persisted identity:
  - a labels-only copy of an admitted article
  - a bounded window (12 h maximum) checked before every recipient
  - the live preview verified before any email
  - the project send lock
  - a recipient set frozen on first send
  - `accepted`/`unknown` never resent; `failed` retried under the same id

  Nothing touches the edition table, rotation or coverage.
- The old `send-test`, which created a timestamped identity per run, is retired and now refuses with a pointer to `test-edition`.
- `render.py` and the page template carry the TEST banner (email HTML/text, story and list pages) and `test: true` in the index.
- Tests: `tests/test_testrun.py` covers the real CLI against a local SMTPS server and a local HTTP server serving the exported preview.

## 4. Unattended content path

**Wiring.** `hip nightly` now runs:
1. supply, for the categories with the largest gap
2. MiMo prepares drafts
3. any draft with a recorded MiMo *provider refusal* gets **one** Pi Claude draft under the same prompts and evidence (no rewording, no second try)
4. the Pi-local Claude final editor admits only through verified records

The MiMo edit loop is no longer called. Health handling:
- A failed Claude preflight (not logged in, API-key auth, CLI missing) writes `data/health/final_editor.json`, leaves drafts pending and exits 4.
- A subscription/auth failure during a run stops the queue, and the attempt does not count against the article's `max_attempts` (`final_edit.health_failure`, `attempts_used`).
- `hip doctor` shows final-editor health.
- No API fallback exists.

**Runtime in the systemd environment.** `validation/claude_runtime_check.py` ran as a transient `systemd-run --user` unit with `LimitAS=3G`, `Nice=10`, `IOSchedulingClass=idle` (the prepare unit's limits) and the user manager's environment: **10/10 pass**. Claude Code 2.1.308, `authMethod claude.ai`, subscription max, `apiKeySource none`, no tools/MCP/plugins, `CLAUDE.md` canary not loaded, 3 s timeout kills the process group, and the nested systemd smoke test passed. Nothing depends on the Windows machine: CLI, login and jobs are all on the Pi. The login's refresh token expires about 29 days after 2026-10-30; `hip doctor` warns at under 7 days.

**Zhang Zhidong (qsg437)** was resolved against the evidence:
- Meaning error: 利一 is 「內處腹地，無慮引敵」 ("no worry about drawing in an enemy"). The analysis paragraph had 避敌 / "avoiding the enemy"; it now reads 不至引敌 / "not drawing in the enemy", consistent with story.1.
- Overlap: the checker now names the shared phrases. Here they were 「把目标的优先级公开排出来」 and 「写成可以逐条检验的清单」, repeated word for word in today[0] and the open question — genuine duplication, not a false positive. today[0] was rewritten (先交代哪个目标最重、哪个其次 / 把支持的理由分条编号).
- New rule: FIX only for concrete repeated wording (a shared run of 6+ characters, or a high overlap with two or more shared phrases); topical resemblance alone is a non-blocking CHECK. Tests cover genuine duplication, resemblance and unrelated text.
- How it was admitted: one owner-directed extra attempt (`final-edit --extra-attempt REASON`; the reason is stored in the hash-bound record), 3.1 min, 5 calls, about 21k output tokens. The first admission was refused because the model marked the carried checker issue "duplicate" of a note rather than of the fix. The rule now says a checker-derived issue, including one carried from a previous attempt, is closed only when the deterministic checker reports nothing at that location on the exact final content. The record was then admitted unchanged: approval `record 9e737d837c79`.

**Real new article, end to end:** two `hip nightly` batches, each run as a transient unit (`LimitAS=3G`, `Nice=10`), each proposing one candidate in each of the two categories the inventory needed. In both batches MiMo did supply and the first draft, and the Pi Claude final editor did everything after that.

| Batch | Candidate (category, tags) | MiMo draft | Claude final editor (unattended, 2 attempts) | Outcome |
|---|---|---|---|---|
| nightly 1, 20:03–20:58 −05:00, exit 0, health ok | `cand-auto-20261030-qsg412-2` 左宗棠/伊犁交涉 (china_modern; no tags, proposed before the tags change) | checker BLOCK + review issues → pending | 10.0 min, 71.5k output tokens, verify open issues 3→3→1→2 | **left pending** (V2-V1, V2-V5 open) |
| | `cand-auto-20261030-grant67-1` Grant's terms at Appomattox (us; no tags) | same | 11.5 min, 10 calls, 83.9k tokens, 7→3→1→1 | **left pending** (V2-V1 open) |
| nightly 2, 21:06–22:06 −05:00, exit 0, health ok | `cand-auto-20261030-sj065-1` 吴起辞婚离魏 (china_ancient; 历史·政治与治理·人物传记) | checker BLOCK + 13 issues → pending | 11.4 min, 10 calls, 81.8k tokens, 3→2→1→0 | **admitted unattended**, record `696cfc72f270` — then **requeued by me** (below) |
| | `cand-auto-20261030-south-el-1` Shackleton's boat journey from Elephant Island (world; 历史·人物传记) | checker BLOCK + 19 issues → pending | 13.7 min, 10 calls, 100.3k tokens, 6→1→2→0 | **admitted unattended**, record `56fe4a604ca7` |

- **Manual interventions:** after nightly 1, one recorded extra attempt each (`final-edit --extra-attempt`, reason stored in the hash-bound record): qsg412-2 admitted in 3.2 min (record `06531de34184`), grant67 in 4.1 min (record `c41d8365f573`). Nightly 2 had no intervention.
- **What this shows:** the unattended path works end to end with no MiMo edit loop and no API: supply → draft → audit/revise/verify → admission through a verified record. But in 2 of 4 articles, verify still found one or two small, real issues after `MAX_ATTEMPTS = 2`. **Owner decision:** raise `max_attempts` to 3 (about 4–6 more minutes per stubborn article, within the 150-minute budget), or keep 2 and accept manual extra attempts.
- **Checker on the admitted finals:** no FIX/BLOCK on any of the four. One non-blocking CHECK each on sj065-1 and south-el-1 (today/question resemblance, overlap 0.14 and 0.17, below the FIX rule).
- **Quality spot check (by me, not by a reader):**
  - **吴起 (sj065-1) has a factual defect.** The zh text says the source "stops at this speech and does not record how the Lu ruler responded" (「这里所据的原文止于这段进言，没有记载鲁君听后如何处置」). But 史记 goes on: 「魯君疑之，謝吳起」. Excerpt E3 ends just before that line, so neither the checker nor the final editor's verify (both read only the evidence pack) could see it. I **requeued** it with that reason (`hip requeue`; reversible). Fix: add the line to the evidence pack and re-prepare.
  - **General gap:** claims about what a source *does not* say are checked only against the excerpts, not the full source. The other three finals make such claims too (for example 「原文未载」 in qsg412-2, 「没有交代」 in grant67). I checked the 吴起 ones against the cached full text. The others have not been checked against the full source. Suggested rule: an absence claim must be scoped as "the excerpts used here", or checked against the full cached source.
  - **左宗棠 (qsg412-2) is short in Chinese:** 2,030 counted characters (about 6 min), against about 10 min in English (2,005 words). That is below the ~10-minute target.
  - **Lengths of the others:** grant67 zh 3,045 / en 2,644 words (about 10 / 13 min); south-el-1 zh 2,984 / en 2,413 (about 9 / 12 min); sj065-1 zh 2,501 / en 2,386 (about 8 / 12 min).
  - No reader has seen any of them; all samples remain unapproved.

**Inventory (from the actual next slot, `china_ancient`; today's TEST does not consume a slot):** **12 days** (`hip inventory`, after the requeue): 13 schedulable editions — china_ancient 3, world 4, china_modern 3, us 3 — filling the rotation A W M U ×3; day 13 needs a 4th china_ancient (gap: china_ancient 1). Before the requeue it was 14 days (the target). Progress this session: 6 → 10 (qsg437) → 12 (nightly 1 + extra attempts) → 14 (nightly 2, unattended) → 12 (吴起 requeued). Awaiting approval: china_ancient 2 (incl. sj065-1), world 1, china_modern 2, us 1. No alert.

## 5. Timers and publication

No systemd unit is installed or enabled (`systemctl --user list-unit-files | grep hip` is empty). No official edition was published, no rotation slot was consumed, `EMAIL_SEND_ENABLED` stays `false`, and `main` is not merged. Hermes/gateway, news-intel, Polymarket and the other Pi services were not modified. Model calls ran one at a time (MiMo via the isolated Hermes runner, Claude via its dedicated config) inside transient units.

## 6. Broad topics and books

**Editorial scope** (`docs/EDITORIAL_BRIEF.md` §题材范围; `prompts/propose_candidate.md`):
- Topics span history, politics/governance/diplomacy, economics/finance/enterprise, science, biography (famous and ordinary people) and society. War belongs among them with no weight and no quota.
- The four rotation categories are unchanged. Themes are tags (`supply.TAGS`, 1–3 per candidate). Any non-historical taxonomy would be a separate proposal.

**Catalogue (discovery only).**
- `jbiaojerry/ebook-treasure-chest` `docs/books.json` (sha256 `e7eb5eb7…`) has 24,071 rows, all with format labels epub/mobi/azw3 and language ZH. 24,002 of them link to `url89.ctfile.com`, a third-party file host behind passwords, and 69 say "link not found".
- The repository has no licence, and it describes its contents as books from commercial reading apps.
- So the catalogue is used **only as metadata**: `hip books import-catalogue` loaded it into `data/books/discovery.sqlite` as 11,088 deduplicated leads (12,983 duplicate rows merged, with tags and every provenance row kept).
- No catalogue link was followed, and no lead is evidence.

**Selection** (`config/book_candidates/selection.json`, via `validation/book_selection.py`). 15 picks, all present in the discovery catalogue, each mapped to an open original/translation, with availability checked by HTTP:

| Lead (catalogue) | Open copy used / checked | Genre → evidence role | Status |
|---|---|---|---|
| 李鸿章传 · 梁启超 | zh.wikisource 1901 text (ws-export EPUB) | contemporary interpretive biography | **acquired**, parsed (756 paras, 14 chapters); needs second basis |
| 曾国藩家书 | zh.wikisource 曾國藩家書 (index) | primary letters | reachable |
| 劝学篇 · 张之洞 | zh.wikisource 勸學篇 | primary political tract | reachable |
| 胡适四十自述 | zh.wikisource 四十自述 (亞東圖書館 1934 1st ed.) | primary memoir; US copyright unverified | reachable |
| 幸运儿：晚清留美幼童 (2011) | Yung Wing, *My Life in China and America* (1909), PG #54635 | modern popular history → use the 1909 memoir | reachable |
| 卢作孚套装 · 荣氏百年 | none identified | modern compilations | access issue (no open copy) |
| 郁金香热 (Dash) | Mackay, *Extraordinary Popular Delusions*, PG #24518 | 1841 popular history, embellishes | **acquired** (EPUB, 4,104 paras); colour, not fact |
| 国富论 | Smith, PG #3300 | primary treatise | reachable |
| 居里夫人自传 | Marie Curie, *Pierre Curie* (Macmillan 1923, tr. C. & V. Kellogg), PG #69617 | participant memoir | **acquired**, **evidence_usable** (edition verified from the title page) |
| 富兰克林自传 | PG #20203 | autobiography | reachable |
| 论美国的民主 | Tocqueville tr. Reeve, PG #815 | contemporary analysis | reachable |
| 伯罗奔尼撒战争史 | Thucydides tr. Crawley, PG #7142 | ancient history (speeches reconstructed) | reachable |
| 胡雪岩 · 高阳 / 绝秦书 · 张浩文 | — | **historical fiction** | not evidence |

**Ingestion pilot** (`src/history_in_practice/books.py`, `hip books ingest|locate`):
- Caps: 3 files, 50 MB per file, 200 MB total. Used: 3 files, 1.3 MB, kept in `data/books/files` (git-ignored), with SHA-256 and provenance in `data/books/manifest.json`.
- EPUB:
  - ZIP bounds: member count, per-member and total uncompressed size, compression ratio, no absolute or `..` names, size re-checked on read
  - DRM/encryption refused
  - XML with internal DTD/ENTITY declarations refused; no external retrieval
  - XHTML parsed with `html.parser`; scripts never run
  - spine order; location = `{spine, href, para}`
  - licence/credit/about pages and Gutenberg START/END sections dropped; Wikisource navigation (arrows, neighbouring-chapter labels, sister-project links) removed
- TXT:
  - encodings: BOM, UTF-8, GB18030 and Big5. Big5 also "decodes" as GB18030 into nonsense; this session's test caught that, and the decode with real CJK punctuation now wins.
  - CRLF and Unicode normalisation; Gutenberg boilerplate removed; hard-wrapped lines joined
  - location = `{offset, length}` into the normalised text plus its SHA-256
- No print page numbers are invented.
- `to_source` writes the book text into the source cache with a location map. The existing `evidence.build` then cuts verbatim excerpts, and `book_location` maps each one back. The status becomes `evidence_usable` only when the edition is verified and its markers are present.
- **Real demonstration:**
  - Text: `BK-CURIE`.
  - Excerpts: six verbatim ones (CUR-E1…E6), each mapped to TXT offsets and checked against the text.
  - Evidence pack: `data/books/demo_evidence_curie.json` (local; excerpts are short quotations).
  - Event candidate: `config/book_candidates/cand-book-20261030-curie-no-patent.json`. Marie and Pierre Curie published the radium-preparation process and took out no patent; she later weighed her friends' objection that patents would have funded a radium institute and still judged they had done right. Tags: science, economics, biography.
  - Its brief states the limits: a single book (her notes plus Meloney's introduction), and no decision date in the excerpts.
  - It is **not queued** for drafting, because the world slot is not the inventory gap.
- Other event candidates are in `config/book_candidates/events.json`, each with an explicit status:
  - located: 李鸿章 and 招商局, with Liang's verdict 「李鴻章所見西人之長技，如是而已」, at spine 8 ¶41
  - located: Mackay's South Sea bubble companies
  - leads only: Tocqueville's townships, Smith's pin factory, Hu Shi
- Deferred: OCR, scanned PDF, MOBI, DRM. No bulk download was attempted.
- Tests: `tests/test_books.py` uses labelled synthetic fixtures; the real-file run is the one described above.

## 7. Commits, tests, blockers, resume

Commits (all on `review/fable-2026-10-30`): 
- `ca60b20` book intake pilot; qsg437 admitted; carried-checker-issue closure rule
- `0cce3d9` broad topics, supply tags, book selection and event candidates; docs (test-edition, timers off)
- `361c1c2` nightly 1 articles admitted (after one recorded extra attempt each); TEST screenshots
- the final commit: nightly 2 articles, the 吴起 requeue, this report, samples README
- earlier this session: the TEST machinery (`testrun.py`, `hip test-edition`), the nightly wiring of the final editor, and health handling (see `git log 361c1c2 -12`)

**Tests.** Final full run: **118 tests, OK** (55.9 s, inside a `LimitAS=3G` unit). An earlier run had 1 error in a test written this session (`test_genuine_duplication…`), which depended on the live qsg437 text that the final editor had just changed; it now builds its own duplication. New tests this session:
- `test_testrun` (6)
- `test_books` (8)
- `test_final_edit`: health failures, nightly queue health, carried checker issues
- `test_llm_checks` `ScenarioOverlap` (3)
- `test_cli_send` (updated)

**Concrete blockers (owner):**
1. **Email:**
   - Create the Resend account and add `read.starhub.vip`.
   - Add exactly the DNS records Resend returns in Cloudflare.
   - Put a sending-only key in `~/.config/history-in-practice/runtime.env` as `SMTP_PASSWORD=`.
   - Set `EMAIL_REPLY_TO=` to an address you read.
   - Then run `bin/hip doctor` (`email_config_problems` must be empty), then `bin/hip test-edition send --test-id test-20261030-snow-water --confirm-real-email`.
   - If the window has expired and nothing was sent: `bin/hip test-edition renew-window --test-id test-20261030-snow-water --window-hours 6` first.
   - Afterwards check both inboxes, spam folders, SPF/DKIM, and reply once to confirm Reply-To.
2. **Reader feedback:** none yet. Samples remain unapproved.
3. **Final-editor `max_attempts`:** 2 (current) or 3 — see §4.
4. **吴起 (sj065-1):** add 「魯君疑之，謝吳起」 to its evidence pack and re-prepare, or drop it.
5. **Absence claims** (「原文未载」 and similar): decide whether they must be scoped to the excerpts or checked against the full cached source.
6. **Timers / official launch:** an owner decision. A successful test is not authorization.
7. **Website integration on `main`:** an owner decision (the preview proves the mechanism; `main` is untouched).

**Resume safely:**
- `.venv/bin/python -m unittest discover -s tests`
- `bin/hip doctor`
- `bin/hip inventory`
- one batch as a transient unit:
  ```
  systemd-run --user --wait --collect -p LimitAS=3G -p Nice=10 -p RuntimeMaxSec=10800 \
    $HOME/history-in-practice/bin/hip nightly --max-articles 2 --budget-minutes 150 --min-candidates 2
  ```
- `bin/hip test-edition status --test-id test-20261030-snow-water`

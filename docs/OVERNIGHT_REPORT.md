# Overnight report — 2026-10-30 (Pi, Claude Opus)

<!-- STATUS: draft, filled during the run -->

## 1. Summary

## 2. Samples and previews

Entry point: `samples/README.md` (tables generated from the files). All four samples are `status: sample`, revision 2, with no BLOCK or FIX findings.

| Sample | Chinese (incl. Q&A) | English (incl. Q&A) | Evidence | Email HTML |
|---|---|---|---|---|
| A 中国古代 · 韩信、陈平、范增：项羽留不住的三个人 | 2,673 字 · ~8 min | 2,682 words · ~13 min | 20 excerpts, one basis (Shiji), disclosed | 41 KB |
| B 世界史 · 拆掉水泵把手，宽街的霍乱就停了吗？ | 2,668 字 · ~8 min | 2,272 words · ~11 min | 20 excerpts, Snow + parish committee | 37 KB |
| C 中国近现代 · 快要毕业时，一百个留学生被叫回国 | 2,534 字 · ~8 min | 2,192 words · ~11 min | 23 excerpts, Yung Wing + Qing history + 1917 alumni record | 39 KB |
| D 美国史 · 欠饷是真的，匿名信也是真的：华盛顿在纽堡站在哪里 | 2,554 字 · ~8 min | 2,002 words · ~10 min | 17 excerpts, Shaw + JCC 24 + Washington text | 36 KB |

Reading time is an estimate at 320 Chinese characters and 200 English words per minute.

- **Chinese runs short:** every Chinese version is a little under the 2,800-character reference. It was not padded; extend only if real reading times come out short.
- **English A runs long:** its English-only tightening call stalled (§5), so it keeps the corrected long version.

Previews:

| Preview | Location |
|---|---|
| Email | `samples/preview/email/sample-X.html`, `.txt`, `.reader1.eml` (fictional `example.invalid` recipients) |
| Site | `samples/preview/site/` (serve with `python3 -I validation/preview_server.py 18767 samples/preview/site`) |
| Screenshots | `samples/preview/screenshots/` (desktop and mobile, zh and en, list, two error states, StarHub nav entry) |
| GitHub-readable | `samples/X/article.zh.md`, `samples/X/article.en.md` |

How they were made: real Hermes runs through the isolated runner (expand Chinese → evidence review → natural English), then editor fixes by Claude, every one logged in `samples/X/editor_log_v2.json`. **Not** written by hand and labelled as automation; also **not** fully automatic, since each sample needed 14–23 logged editor changes.

## 3. Code

`src/history_in_practice/` (stdlib + `opencc-python-reimplemented`), CLI `bin/hip`:

| Module | Responsibility | Status |
|---|---|---|
| `sources` | Fetch per adapter (`wikisource_render`, `archive_djvu`, `html`), classify `evidence_usable / extractable / challenge_page / wrong_url / site_fallback / http_error`, cache text + SHA-256 | real (used for every sample) + local tests |
| `evidence` | Verbatim excerpts cut by start/end anchors, with offset and source hash; canonical spans for the registry | real + tests |
| `registry` | Immutable episode IDs, `parent_event`, alias / 繁简 / QID-redirect normalisation, source-span overlap, CJK bigram FTS + `instr`, active-status coverage, unique core span, rebuild from content | tests (13 dedup cases ported) |
| `llm` + `hermes_isolated` | Project-level isolated Hermes call (0 tools, no SOUL/memory/AGENTS), prompt on stdin, process-group timeout, live output cap | real (all model calls tonight) + tests with a fake runner |
| `checks` | Evidence IDs, classical quotes (繁简) and English quotes (verbatim) against cited excerpts, English numbers absent from Chinese = BLOCK, structure | real + tests |
| `render` | One object → email HTML/text, site JSON + index, GitHub Markdown; `content_sha256` over both languages, Q&A and sources | real |
| `state` | SQLite edition state machine, frozen content, per-recipient deliveries keyed by salted hash, `recover()` turns `sending` into `unknown` | tests |
| `mailer` | One SMTP sender (SMTPS/STARTTLS), per-recipient `accepted / failed / unknown`, stable Message-ID, send gate | local (SMTPS fixture) |
| `site_export` | Allow-listed export (`history/`, `data/history/`), live check by JSON + revision + recomputed hash + both languages | local fixtures; real site pending |
| `publish` | schedule by rotation → archive to `content/` → commit website copy → verify live → email; resumes in-flight editions | local end-to-end test |
| `pipeline` | candidate → fetch → evidence → admission → registry → Hermes ×3 → assemble → checks → inventory or pending | real (2 candidates) + mock tests |
| `cli` | `doctor --probe`, `prepare`, `prepare-queue`, `check`, `render`, `export-site`, `verify-site`, `send`, `retry-send`, `publish-today`, `status`, `inventory`, `recover`, `registry-rebuild` | real for doctor/render/export/prepare-queue |

Website: `deploy/website_test/0001-*.patch` adds `history/`, `data/history/` and one nav link (1 line in `index.html`, original line endings kept). Committed on a local branch in `data/website_test` (git-ignored); **not pushed**, because a pushed branch could trigger a Cloudflare preview build whose deploy command is unverified.

systemd: `deploy/systemd/hip-{prepare,send}.{service,timer}` templates, LA time zone, batch budget for preparation, `LimitAS` (the user cgroup ignores `MemoryMax`). **Not installed, not enabled.**

## 4. Verification

Legend: **real** = ran for real on the Pi (real Hermes model, real network fetch, real files); **local** = local simulation with fixtures (local SMTPS server, fake site); **implemented** = code exists and is unit-tested but not exercised end to end; **pending config** = blocked on an outside account or permission.

| What | How | Result | Class |
|---|---|---|---|
| Hermes isolation | `hip doctor --probe`: real Hermes entry point, `chat` replaced, no model call | 0 tools, no SOUL, no memory, no cwd AGENTS canary | real |
| Hermes calls | 32 calls tonight through the isolated runner (12 stage 1 earlier, 14 stage 2, 1 tightening, 2×3 candidates) | see §5 | real |
| Runner bounds | fake runner: valid, error exit, empty output, hang with a grandchild, 5 MB flood | timeout kills the whole process group; output cap stops the flood while running | local (`tests/test_llm_checks.py`) |
| Sources | 31 documents fetched and classified per document | challenge (ctext, Founders), 403 (loc.gov), 404, site fallback (starhub), reachable-but-irrelevant all detected | real (`validation/fetch_results.json`) + local (`tests/test_sources.py`) |
| Evidence | 80 excerpts for the samples, plus 21 for the candidates, cut by anchors | every quote is an exact span; missing anchors and unusable sources are refused | real + local |
| Dedup | retitle, English names, 繁体, aliases only, other category, QID redirect, missing QID, prepared-not-published duplicate, racing insert, same parent event / different episode, same person-year-place / different decision, other-work paraphrase → review, rebuild from content | all pass | local (`tests/test_registry_pipeline.py`) |
| Checks | missing evidence id, unknown id, invented English quote, English number absent from Chinese, today-scene repeating the question | BLOCK/FIX as designed; all four samples pass | local + real |
| Pipeline | mock model: good candidate → inventory; missing source → pending while others continue; duplicate → rejected; model timeout → pending without a second full timeout | all pass | local |
| Publish flow | temp content dir + temp website git repo + live check served from it + local SMTPS: stop after archive → resume without rewriting; only allow-listed files committed, `articles.html` untouched; one recipient refused → partial → retry sends only that one; stale live copy blocks email; no ready edition in rotation category → skip | all pass | local (`tests/test_publish.py`) |
| Site verification | 200 homepage fallback, old revision, same id/title with changed body (hash), missing English | all rejected | local (`tests/test_site_verify.py`) |
| SMTP | CLI `hip send --local-smtp` against local SMTPS with 3 fictional recipients | run 1: accepted / failed (RCPT 550) / unknown (drop during DATA); run 2: only the failed one resent, unknown not resent; exit 3 while any is not accepted | local (`data/logs/local_smtp_demo.txt`) |
| Email size | rendered long samples | HTML 37–42 KB, text 27–32 KB (budget 90 KB) | real render; **real client display not tested** |
| Site page | headless Firefox screenshots of the history page, tabs, mobile, errors; local StarHub copy with the new nav link | renders; fallback and missing story show an error banner | local |
| Real email delivery | — | not attempted (no Resend account/key; sending disabled) | pending config |
| Cloudflare deployment | — | not attempted; website change kept as a local patch | pending config |

`.venv/bin/python -m unittest discover -s tests` → 39 tests, all passing at the last checkpoint.

## 5. Model timings

## 6. Recovery and run commands

```bash
cd /home/star/history-in-practice
git fetch && git checkout impl/overnight-20261030      # same commits as PR #1 branch review/fable-2026-10-30
.venv/bin/python -m unittest discover -s tests          # all tests
bin/hip doctor --probe                                  # env, isolation probe, private config (set/unset only)
bin/hip status ; bin/hip inventory                      # editions, deliveries, inventory
bin/hip recover                                         # interrupted sends -> unknown (never auto-resent)
bin/hip prepare-queue --max-articles 2                  # run queued candidates (config/candidates/*.json)
bin/hip render samples/*/article.json --out /tmp/hip-preview      # email html/txt/.eml (fictional To), site data
python3 -I validation/preview_server.py 18767 samples/preview/site  # local site preview (port 8765 is taken)
```

If a job died mid-run: rerun the same command. Fetches are cached in `data/source_cache`, the episode registry and edition states are in `data/hip.sqlite`, and `publish-today` resumes from the last recorded step without regenerating or re-archiving the article. A delivery left in `sending` becomes `unknown` and is reported, not resent; resend only after checking the recipient's inbox, using `retry-send` (which only touches `failed`).

To rebuild the registry from committed content after losing SQLite: `bin/hip registry-rebuild content/**/*.json` (and `samples/*/article.json` for the samples).

## 7. Must configure tomorrow morning

1. **Resend**: create the account, add the sending subdomain `read.starhub.vip`, add exactly the DNS records Resend returns in Cloudflare DNS (do not touch the root domain's existing mail or web records), wait for verification.
2. **Sending key**: create a key limited to sending (and to that domain if offered). Put it only in `~/.config/history-in-practice/runtime.env` as `SMTP_PASSWORD=` (file stays mode 600). Keep `EMAIL_SEND_ENABLED=false` until a manual test send.
3. **Optional Reply-To**: set `EMAIL_REPLY_TO=` in the same private file if replies should reach a real inbox (the From address has no mailbox).
4. **Recipients**: already in the private file (2 addresses); nothing to add unless they change.
5. **Website**: confirm how starhub.vip deploys (Cloudflare Workers/Pages, production branch, build command), then decide whether to push `deploy/website_test/0001-*.patch` as a website PR. Set `SITE_REPO_PATH` (a clean working copy) in the private file; leave `SITE_PUSH_ENABLED` unset until you approve automatic site commits.
6. **First real test**: `bin/hip send samples/D/article.json --real` only after steps 1–3, then check both inboxes (Gmail and QQ), spam folders, SPF/DKIM and layout in each language.
7. **Timers**: only after the above, follow `deploy/systemd/README.md`.

## 8. Not done / open issues

1. **No real email, no deployment, no timers.** By instruction. Resend, the DNS records and the key come first (§7).
2. **Inventory is far below 14 days.** See §1 for tonight's count. Each automated article costs about 10 minutes of model time. Automated drafts that pass the gates still contain errors a reviewer would catch, and the samples needed 14–23 logged editor changes each. Until reader feedback says otherwise, plan on an editor pass before scheduling, or accept a lower bar knowingly.
3. **Sample A's English is about 13 minutes** (estimated), longer than the other three. The tightening call stalled. Rerun it with `python3 -I validation/tighten_en.py A`, or trim by hand.
4. **Chinese length runs about 8 minutes** (2,534–2,673 characters), under the 2,800-character reference. It was deliberately not padded; calibrate with real readers first.
5. **Hermes behaviour.**
   - About 1 in 5 long calls returned invalid JSON. Retry or the trailing-comma fallback recovered every one, but that leaves no slack.
   - One call stalled for 19 minutes with no output.
   - Keep per-call timeouts of 20–30 minutes and the per-article budget; consider a shorter English-only timeout (10 minutes) since English calls normally take 2–4 minutes.
6. **Isolated runner depends on Hermes internals** (`AIAgent` constructor arguments). Rerun `bin/hip doctor --probe` after any Hermes upgrade.
7. **Production news-intel still calls `hermes -z … -t "" --ignore-rules`**, which enables 29 tools with auto-approval. That is outside this project and was not changed; it is the user's decision.
8. **Website change is a local patch**, not a PR on `website_test`. Deliberately unpushed: a pushed branch could trigger a Cloudflare preview build whose deploy command is unverified.
9. **Translation mapping for dedup.** Spans are compared within the one configured edition of each work. A translation must be mapped to the original work's reference before it can be compared. Same-episode retellings from a different work and without a QID only reach `review`.
10. **Log rotation** is a size warning in `hip doctor`, not automatic rotation.
11. **Real email-client rendering** (Gmail, QQ Mail, Apple Mail) is untested; only the HTML size and structure are verified.

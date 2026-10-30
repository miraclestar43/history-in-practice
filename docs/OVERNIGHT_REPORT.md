# Overnight report — 2026-10-30 (Pi, Claude Opus)

<!-- STATUS: draft, filled during the run -->

## 1. Summary

## 2. Samples and previews

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

Legend: **real** = ran for real on the Pi (real Hermes model, real network fetch, real files); **local** = local simulation with fixtures (local SMTPS server, fake site); **implemented** = code exists and unit-tested but not exercised end to end; **pending config** = blocked on an outside account or permission.

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

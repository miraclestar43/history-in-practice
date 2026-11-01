# Proposal and staged handoff: 3-minute news with 没事儿多读书

Owner request, 2026-10-31 (America/Los_Angeles): consider delivering a three-minute current-news brief with the daily reading edition and strengthen the existing miraclestar43/news-intel project.

This is additive to the active reader-first sample. Do not stop or restart the current 胡适 job, substitute news work for delivering that sample, or revive Snow. This file defines a concrete integration plan; it does not claim the integration is implemented and does not authorize additional real sends, production timer activation, main merge or changing the existing news delivery schedule.

## 1. Product proposal

One reading email, two clearly separated modules:
1. 今日新闻 · 3 分钟 — a short Chinese current-news section.
2. 今日故事 · 约 10 分钟 — the original bilingual history/practice article, retaining its factual and reader-experience standards.

Give clear anchors so the reader can jump directly to either. Keep the brand and subject format:
没事儿多读书｜YYYY.MM.DD｜{specific story title}
The brief can appear in the preheader/intro, not as a long list of headlines in the subject.

Default news prototype: Chinese in the email; an equivalent English short brief may be offered on the webpage's language tab, rather than automatically doubling the new news section in the email. This is a proposed default, not a change to the requirement that the story itself has full Chinese and English.

News time label must be explicit, e.g. 截至当日07:00（洛杉矶时间），过去24小时要闻. "Today's news" is not a promise to cover events that have not happened yet. Use timezone-aware dates and existing event/published-at semantics.

## 2. Existing implementation inspected

Repository: https://github.com/miraclestar43/news-intel, main.
Current repo inspection includes README, config/policy.yaml, config/editions.yaml, compose/enrich prompts and selected daily/evidence/validation paths.

Already present:
- collection from roughly 25 configurable RSS/API/HTML sources;
- exact and event-level deduplication, source-family confirmation;
- ranking/materiality/freshness and daily selection;
- separate en_global and zh_cn editions;
- bounded evidence-driven enrichment, validation and deterministic fallback;
- Telegram delivery/state/allowlists and daily production entry points.

Important limits:
- config/policy.yaml's existing Chinese daily target is 2,800–3,800 characters and daily selection 4–8 events. This is a configuration target, not a measurement of today's live output. It is not the requested three-minute profile.
- en_global is configured for 22:00 Pacific and zh_cn for 07:00 Pacific. The history project's intended morning send is 07:30 Pacific; verify actual Pi configuration rather than asserting those production timers are currently active.
- Source code and README are not proof of current source health, provider configuration, recent editorial quality or actual delivery. Check recent real artifacts before changing the pipeline.

Reuse these capabilities; do not start a third independent collector or copy this repository inside the history repository.

## 3. Short-news editorial profile

Target roughly 600–900 Chinese characters including the short explanatory prose, a loose 2–3-minute reading reference. Select 3–5 events, fewer on a genuinely quiet/poorly sourced day. Do not pad or enforce a fixed category quota.

Each item:
- a short plain-Chinese headline;
- what actually happened, in one or two clear sentences;
- why it is worth knowing, one specific, supported sentence or clearly labelled interpretation;
- one or two directly relevant reader-facing source links;
- uncertainty/date qualifiers retained where necessary.

Selection:
- prioritize material China/world developments and relevant AI/technology/semiconductor/economic events, with variation and importance ahead of rigid slots;
- no clickbait, trivia, routine company promotion or sheer popularity;
- one event is one item even if many outlets repeat it;
- cross-day repetition requires a meaningful new development and an explicit update;
- distinguish announced/proposed/approved/effective, source publication time/event time and preliminary/confirmed outcomes;
- define unfamiliar names and technical terms; avoid several actors, ticker symbols and numbers in every sentence;
- the digest must offer a useful selection/explanation, not merely concatenate RSS titles or copy lead paragraphs.

Do not forcibly connect each day's news to that day's historical story or turn historical analogies into predictions.

## 4. Minimal technical seam

news-intel owns collection, events, news evidence, confirmation, selection and the short-news snapshot.
history-in-practice owns the reading edition, article, combined rendering, website export and email delivery.

Add a small, versioned local export/consume interface:
- stable snapshot identity/revision, language, intended edition date, timezone, generated/as-of time, window boundaries, readiness/degraded status;
- 3–5 selected event items, their fact/interpretation text, source identities/URLs and confirmation qualifiers;
- provenance back to the existing news event/evidence records and code/prompt version where already available;
- atomic write and a consumer-side schema/freshness check.

Avoid sharing writable SQLite internals or having the history app operate news-intel's database/schema directly. Reuse read-only/export paths where present.

Morning flow:
- generate the short-news snapshot from genuinely current qualified events near the agreed cutoff;
- combine with an already-reviewed story, without asking the history editor to regenerate current news;
- preserve a frozen snapshot identity in the combined preview/send record;
- same final content goes to email and corresponding web edition.

Do not prepare tomorrow's current news with the previous evening's history batch. Do not make every email send call rerun model composition or selection.

Failure boundaries:
- stale, absent or unsafe news does not become a purportedly fresh brief;
- publish no fabricated filler. The reading edition can proceed without news, with an honest short unavailable/degraded note if appropriate;
- do not silently insert yesterday's section under today's heading;
- news generation/export must not send a duplicate Telegram or email message;
- leave accepted/unknown delivery rows intact on retries.

Existing Telegram outputs remain unchanged during the prototype. Any decision to remove duplicate future channels is separate from this feature; do not disable the reader's existing service silently.

## 5. Strengthen quality before connecting delivery

First perform a bounded, read-only audit on the Pi:
- actual checkout/head, service state, source health and recent real en/zh outputs;
- whether LLM editorial enrichment was actually used or deterministic fallback ran;
- stale links, truncated text, translation quality, major omissions, repeated events and unsupported significance claims;
- whether scoring over-selects small technical stories and displaces important general developments.

Inspect three recent actual daily snapshots/days if available, not three manufactured fixtures. Report evidence honestly if there are fewer. Do not fetch unrelated private files or print keys, chat IDs or email recipients.

Implement the short-news profile in an isolated feature branch using docs/GIT_WORKFLOW.md. Preserve the production checkout, existing systemd units, delivery authorization and Telegram credentials. No shared Hermes upgrade or new paid provider/account.

Validation should cover the real integration risks:
- unsafe/stale snapshot refused or omitted without losing the story;
- false success/empty output not reported as a three-minute briefing;
- source/uncertainty qualifiers preserved;
- repeated event suppression and meaningful updates;
- morning date/window/DST correctness;
- frozen combined version and no duplicate send behavior;
- combined email/mobile rendering and actual HTML byte budget.

Use the actual existing test suite/checks appropriate to changed code; fixtures must be fictional and never contact recipients.

## 6. Small deliverable

After the current story sample reaches a checkpoint:
1. Audit recent news artifacts and identify the highest-impact quality fixes.
2. Produce ONE real three-minute news snapshot from current qualified events, without sending.
3. Render ONE combined reading-email preview and website preview with anchors.
4. Provide reading estimates and actual bytes, source traceability and freshness status.
5. Obtain reader feedback on the actual preview before any recurring production integration.

No requirement to finish a new automation platform, rebuild the entire news project or consume all article inventory first.

## 7. Other useful features, in priority order

- A discoverable “没事儿多读书” entry and dated story/news archive, with a direct reading permalink.
- Lightweight reader feedback: interesting / too hard / already familiar / want more. Initially support existing reply-based feedback; do not add fake nonfunctional buttons or expose private reply addresses in public Git.
- Topic/region filtering in the archive, retaining the China-led story preference independently from news selection.
- Browser-local saved/continue-reading state where useful; label its device-local limits honestly.
- Optional audio later, after readable text and reliable delivery work. Do not make speech generation or account systems a launch prerequisite.

The immediate priorities remain the fresh Chinese story sample, evidence correctness and reading experience. The three-minute section should add a small daily information benefit without turning the email into another overloaded feed.

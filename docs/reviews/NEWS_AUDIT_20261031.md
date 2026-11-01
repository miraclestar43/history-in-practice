# news-intel: read-only quality audit for the 3-minute news module (2026-10-31, prompts/08 §5–6)

**What was touched:** nothing changed in news-intel.
- The production checkout `~/pi-news-intel` (`main` @ f97b73c) was read.
- Its database was opened with `mode=ro`.
- systemd timers and the journal were listed, nothing more.
- No service, timer, `.env`, Telegram setting or Hermes setting was changed, and nothing was sent.

**Scope:** the last 6 real daily runs per edition (digests 131–140, 2026-10-26 … 10-31) and the events in the 24 h up to 2026-10-31 16:00 PT. These are real artifacts, not fixtures.

## Findings

| # | Finding | Evidence |
|---|---|---|
| 1 | **The Chinese daily ran on the deterministic fallback every day**, including 10-31, the day after the Hermes model fix. | `digests.model_used = 'none (deterministic fallback)'`, `fallback_used = 1` for zh_cn 132–140; `job_runs.detail_json` says `fallback_used: true`. The English daily used `hermes-cli` on 10-31 only (139); 131–137 were fallback too. |
| 2 | **The reason for each fallback is not logged.** | `job_runs` records only that a fallback happened; the journal has no provider-outcome line. This is also noted in the project's CURRENT.md. |
| 3 | **The Chinese daily comes from two tech outlets only**, so it shows 2–4 items despite 36–74 "qualified" events. | Every zh digest ends with "全部来自 2 家媒体；受单一来源上限限制，实际展示 2 条" (IT之家, 量子位). |
| 4 | **Scoring over-selects small tech and consumer items and buries major general news.** In the 24 h window, phone launches, chargers and earnings score 59–71. Major general stories are "Unclassified" and score about 39. | 113 of 238 window events are `Unclassified`. Examples: "More than 5,000 die from Ebola in DR Congo's deadliest outbreak" (BBC, 38.8); 山东海阳核电三期开工 (45.0); the $6.3B Binance hack (45.0); "Thousands demonstrate in Paris" (38.8). Meanwhile "129 元 … 氮化镓充电器上架" scores 61.3. |
| 5 | **The fallback text is the source's lede pasted in.** | It includes "（IT之家注：现汇率约合…）", an English date ("每日情报简报 — Oct 31") inside the Chinese brief, and the label "本简报基于规则排序的信息来源摘要". |
| 6 | **Category errors.** | "谷歌 Alphabet 盘初跌超 13%" is filed under 中国经济与政策 (digest 136). |
| 7 | **The English brief is mostly tech earnings and market moves**: OpenAI, Intel, CXMT, Alphabet, Twilio, Pinterest, Coinbase. On 10-30 and 10-31 it carried 0–1 general-world items. | digests 137, 139. |
| 8 | **Link and text defects in the English brief.** | 137: a lede is cut mid-phrase ("…but a who's."); a MarketWatch item links to the site homepage (`https://www.marketwatch.com/`) rather than the article. 139: the brief says "rule-ranked source summaries" although `model_used = hermes-cli`. |
| 9 | **The delivery label may be wrong.** The 14:01 UTC (zh) deliveries are recorded with `edition_id = 'en_global'`. | `deliveries` rows at 14:01 UTC on 10-28 … 10-31. Needs a code check before calling it a bug. |
| 10 | **The schedule does not match the history send.** The zh daily runs 07:00 PT and the history send is planned for 07:30 PT. The en daily is still fixed at 05:00 UTC, so it moves to 21:00 PST after DST ends on 11-01. | `systemctl --user list-timers`; CURRENT.md. |

**Other events (outside news-intel):** the Pi rebooted unexpectedly on 2026-10-31. The previous boot's journal ends at 17:36:21 CDT with no shutdown sequence, and there is no OOM, under-voltage or watchdog message. The cause is unknown.

## Highest-impact fixes (proposed; not implemented in news-intel)

1. **Log the provider outcome per daily run** (model, error or empty output, why it fell back). Without this, finding 1 can't be diagnosed. Then make the zh path actually use the model when Hermes works.
2. **Add general Chinese and world sources to the zh pool and classify them.** Fix the Unclassified bucket before ranking, so a 5,000-death epidemic outranks a charger. The source cap should diversify the selection, not shrink it to 2 items.
3. **Add a short-news profile** (3–5 items, 600–900 zh characters, importance and variety ahead of score), exported as a frozen, versioned snapshot. The schema used for the sample is `samples/news/news3min-20261031-1600PT.json`. This work belongs in a news-intel feature branch, per its docs/GIT_WORKFLOW.md.
4. **Strip publisher boilerplate** ("IT之家注…") and use localized dates. Reject homepage-only links and mid-word truncations.

## The sample in this round

[`samples/news/news3min-20261031-1600PT.json`](../../samples/news/news3min-20261031-1600PT.json):
- **Window:** the 24 h to 2026-10-31 16:00 America/Los_Angeles.
- **Selection:** 5 items, chosen *by the operator* from news-intel's own events for importance and variety (a prototype, not the automated profile).
- **Length:** 725 zh characters, about 2.3 min at 320 chars/min.
- **Sourcing:** every fact traces to a listed source stored by news-intel; uncertain points are kept (anonymous sources, Binance's own claim, North Korea as a *suspect*).
- **Delivery:** not sent anywhere.

## Follow-up (2026-10-31 night): branch `feature/news3min-quality` in news-intel

**Status:** implemented and validated offline, **not merged**. Services, timers, Telegram and `main` are unchanged. Full report on the branch: `docs/NEWS3MIN_QUALITY_20261031.md`, commit `bd364a2`, worktree `~/pi-news-intel-wt-news3min`.

- **Why zh falls back (findings 1–2):** every run now records its provider outcomes. A real run of 5 stories showed the provider answers, but the validator rejects correct Chinese output:
  - IT之家 amounts such as `32 万亿日元` were not traceable. **Fixed.**
  - The model writes English entity names for Chinese sources. **Open:** needs a bilingual alias table.
- **Where general news is lost (findings 3–4):**
  - **Collection:** the zh edition has no general news source.
  - **Classification:** about 830 events per edition per week are Unclassified, with relevance multiplier 0.0.
- **Ranking fix:** a public-safety bucket behind a flag that defaults to off. Replayed on the 240 real events of the window: Ebola goes from 38.8 (cannot qualify) to 66.0 (qualifies; above the charger's 61.3), and no other event changes.
- **Automatic snapshot (no human choice):** produced for comparison.
  - In `samples/news/`: `news3min-auto-20261031-1600PT.flag-off.json` and `.flag-on.model.json`.
  - With the provider, 2 of 5 items were model-validated, but both contain errors that validation did not catch. So it is **not reader-ready**.
  - The hand-picked sample (`news3min-20261031-1600PT.r2.json`) shows editorial direction only.
- **Owner decisions:**
  - add general Chinese/world sources (source policy);
  - the 0.0 Unclassified multiplier;
  - enable the flag;
  - merge.

## Copy fixes in the sample (revision 2, owner feedback)

`samples/news/news3min-20261031-1600PT.r2.json`; revision 1 is kept.

- **"Why" lines:** each is grounded in a source or omitted. Ebola now has none, because its source adds nothing to the headline.
- **Labels:** each "why" line carries its kind: 为什么值得知道 (reported), 来源观点 (a named source's judgment) or 编辑解读 (the editor's reading). `news_problems` rejects an unknown kind, or a "why" that restates the headline.
- **No links between stories:** the OpenAI funding cut, the stock drop and the memory-chip profits are no longer linked as a trend. The memory-chip "why" is 日经亚洲's own explanation, attributed to it.
- **Data comparisons:** keep the period (July–September 2026; Micron June–August), and say that Apple's part is a market forecast, not an actual figure.
- **Cross-day events:** Binance gives the date of the hack (10-29) and what was new on 10-31 (90% covered).
- **Count:** 5 items, 764 zh characters, about 2 minutes. OpenAI dropped out to keep 5 items with variety.

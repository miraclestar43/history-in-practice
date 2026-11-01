# Reader-first rules in the writing agent (2026-10-31)

Owner request: put the 吴起 reader feedback into the prompts the agents actually load: the MiMo draft, the English and the Claude final review. Remove conflicting older rules, cover every call path, and prove it with the 吴起 fix plus a new Chinese story from an existing evidence pack.

## One rule file, loaded by every stage

**The rules.** `src/history_in_practice/prompts/reader_first_zh.md` holds them once, in 15 rules:
- People and titles:
  - introduce a person only with what the reader needs at that moment;
  - bring people in as the plot needs them;
  - keep same-title people apart (two princesses, successive rulers or chief ministers);
  - make referents in adjacent sentences unambiguous.
- Turning points: who did what, who saw it, and why another person read it differently, without invented thoughts.
- Classical lines: explain each one in place, including the job it does in the exchange.
- Record, judgment, inference:
  - no review-process notes or repeated "（作者解释）" in the body;
  - keep record, a named person's judgment and author inference apart, in natural sentences.
- Dek and hook: the dek invites; the hook unfolds the situation; neither retells the plot.
- Modern scene: one short scene, in the open question.
- English: the same rules apply.
- Fixes: no re-adding material that was cut.

The English version is `prompts/reader_first_en.md`.

**How it is loaded.** `pipeline.load_prompt(name)` expands `{{include:x}}`. Every stage loads its prompt through it.

**What is recorded.** Every model call records `prompts` (file + sha256) in `calls.jsonl`, in the final-editor record and in the context-review record. The list is computed from the text that was actually sent, so it shows what each call received, not what the docs say.

| Stage (who) | Code | Files actually sent (recorded per call) |
|---|---|---|
| Chinese draft (MiMo) | `pipeline.run_model_steps` step `draft_zh` | `style_zh.md` + `reader_first_zh.md` + `draft_zh_long.md` |
| Fact review of the draft (MiMo) | step `review_zh`; editor `rereview_r*` | `review_zh.md` (fact review; now also counts same-title confusion, and must not ask for biography back) |
| English (MiMo) | step `en` | `translate_en_long.md` + `reader_first_en.md` |
| Edit rounds (MiMo) | `editor.edit` → `edit_r*` | `edit_zh_en.md` + `reader_first_zh.md` (rule 9: fixes must keep the rules, rule 15: no re-adding) |
| English parity (MiMo) | `editor.reviews` → `parity_r*` | `parity_en.md` (an ambiguous English referent is now a content difference) |
| Final audit (Claude) | `final_edit.run` → `audit` | `final_audit.md` + `reader_first_zh.md` |
| Final revise (Claude) | `revise_r*` | `final_revise.md` + `reader_first_zh.md` (only the sentence at issue; no re-adding) |
| Final verify (Claude) | `verify_r*`; also `local_fix` | `final_verify.md` + `reader_first_zh.md` (re-added cut material is a fix) |
| Owner-authorized revision | `hip revise-base` → `final_edit.run` | same as the three rows above |
| Local fix | `hip local-fix` → `final_edit.local_fix` | `final_verify.md` + `reader_first_zh.md` |
| Source-context review (Claude) | `context.review` (pre-draft and on the final text) | `context_review.md` (now: list only omissions that change the reader's judgment; no biography) |

**Conflicts removed:**
- `draft_zh_long.md` required "today 恰好两段" with two scenes different from the question. Now: today is off by default, the one modern scene sits in the question, and an optional today is one paragraph with no new scene.
- `style_zh.md` repeated that rule. Fixed.
- `docs/PLAN.md` said "两个具体启发，各配一个现代小场景". Superseded.
- Three duplicated 讲清楚 blocks (style, audit, verify) and a fourth condensed copy (revise) are replaced by the shared file.

**Checker** (advisory CHECKs; facts unchanged):
- a two-paragraph today (the older admitted format, so not a FIX);
- a dek that repeats hook[0]'s wording.

**Tests** (`tests/test_final_edit.py`). Each path is driven with a recording fake and must carry the rules:
- prepare, edit, final audit/revise/verify, local-fix, the owner revision and context;
- the call records must name the files;
- the old conflicting rules must be absent.

Full suite: 174 OK.

## Acceptance 1: 吴起 revision 3 (the final editor applies the rules)

**Setup.** The base is rev2's text, unchanged, run through one owner-authorized `revise-base` attempt. Rev2 is archived in `samples/auto/cand-auto-20261030-sj065-1/revisions/rev2/`.

**What the new audit found.** The final audit (final_audit.md + reader_first_zh.md) raised, unprompted:
- F1: the dek named 吴起, 田文 and 公叔 and told the whole trap and its ending.
- F2: hook.0 told the ending, then story went back over it.
- F3: "公主" in story.5 did not say which of the two princesses.
- F4: the English "slight him" could mean 公叔 or 吴起.
- Notes: Wey/Wei; uncertainty note repeating limits.

The old prompts had passed this text.

**Revise and verify.** Revise fixed F1–F4. Verify then raised:
- V1: hook.1 repeated the dek.
- V2-V1: the dek's "当时的宰相" read as 公叔 (two successive chief ministers).
- V2-V2: "他严明法令" could be 楚悼王 or 吴起.

**Local fixes** (standing rule, quote-backed):
- **V2:** "魏国的前一任宰相"; "吴起严明法令"; "the new king".
- **V3**, three older rev2 issues the verify pass found:
  - the order of 吴起's three comparisons. The source reads 將三軍 → 治百官 → 守西河 (checked in the cached text);
  - E20 added to hook.0;
  - 李克 is not a "当事人".
- **ctx:** the context review cut E29 (文侯以為將，擊秦，拔五城) into story.0.
- **Refusals:** two attempts were refused by the scope guard (out-of-field ev change; an id-less context issue) and kept as logs.

**Result.** Verify clean, context review clean, admitted (record `1948ffd0a5cb`). zh 2,193 chars ≈7 min; en 1,748 words ≈9 min.

**Not raised by the final editor:** context.1's 鲁国 backstory is still long.

## Acceptance 2: new story from an existing evidence pack (信陵君救赵, `cand-auto-20261031-sj077-2`)

**Pack.** The sj077-1 pack, including its earlier context-review additions (30 excerpts, byte-identical). The pre-draft context review added E35–E38.

**Why this pack.** It is the hardest available test of the people rules:
- seven named actors;
- two men called 公子 (信陵君 and 平原君);
- three kings, plus a later 魏王;
- 平原君's wife is 无忌's sister;
- 如姬, the king's favourite.

The episode is textbook-familiar, so it is a validation piece, not a reader-sample proposal.

**sj077-1.** It was drafted under the old prompts and is superseded: its episode was released and its edition rejected with the reason (`data/logs/sj077_supersede.py`). All of its records are kept.

**Chain, as recorded per call:**

| Step | Model | Prompt files (from `calls.jsonl` / records) | Result |
|---|---|---|---|
| context pre-draft | Claude | context_review.md (recorded once the template fix landed; this first call shows `[]`) | +E35–E38 |
| draft_zh | MiMo | style_zh.md, reader_first_zh.md, draft_zh_long.md | 550 s |
| review_zh | MiMo | review_zh.md | 12 fix/block issues |
| en | MiMo | translate_en_long.md, reader_first_en.md | 1st reply not JSON; 2nd ok |
| edit_r1/r2, rereview, parity | MiMo | edit_zh_en.md + reader_first_zh.md; review_zh.md; parity_en.md | 49 edits, 11 left |
| final attempts 1–3 (audit/revise/verify) | Claude | final_*.md + reader_first_zh.md, every call | attempt 3 admissible |
| context review | Claude | context_review.md | needs work: A2/A3, E39 |
| local fix | Claude verify | final_verify.md + reader_first_zh.md | clean; context clean; admitted (`43b8e15206ba`) |

**What the MiMo draft already did under the new prompts:**
- the dek is a situation, not an ending;
- the hook is a scene at 夷门;
- 「无忌的姐姐是平原君夫人」, 如姬 「最得魏王宠爱」;
- it calls 信陵君 "无忌" throughout, which avoids the two-公子 problem;
- 晋鄙's turn is complete: the tallies match, but "一辆车来接替我" makes him suspicious.

**What the final editor added (readability issues, all fixed):**
- 侯嬴 given an identity at first mention;
- context restating the hook cut;
- evidence ids in the body removed;
- 信陵君/无忌 and 赵胜/平原君 tied together;
- 毛公/薛公 introduced;
- the turning answer 「以肉投餒虎」 moved from analysis into the story;
- the English Prince Wuji / King Anxi made "of Wei";
- the 魏王 captured 18 years later distinguished from 安釐王.

**Remaining** (notes, not blocking):
- four classical lines are quoted without a plain gloss (「嚄唶宿將」「此五霸之伐也」「意驕矜而有自功之色」「立自責，似若無所容者」). A local fix was refused because the text was already admitted with nothing open. The audit/verify prompts now rate this as a fix;
- "作者推断" repeated in analysis.0–3;
- context.0–3 partly restating hook.1;
- the English is 2,946 words (≈15 min) against a ~10 min target: MiMo's English expands, and nothing in the chain trims it.

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

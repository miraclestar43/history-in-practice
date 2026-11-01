#!/bin/bash
# Standing owner rule (2026-10-31): the sj077-2 context review (after attempt-3 was admissible): A2/A3 "not recorded states
# of mind" is an unverifiable negative -> state positively that the phrases are the historian's narration (zh and en, for
# parity); its cut excerpt E39 names the friend Hou Ying visited as 朱亥 (relationship needed later) -> context.5.
cd "$HOME/history-in-practice" || exit 1
systemd-run --user --wait --collect --pipe -q -p LimitAS=3G -p Nice=10 -p RuntimeMaxSec=3600 --working-directory="$HOME/history-in-practice" \
 bin/hip local-fix cand-auto-20261031-sj077-2 --changes data/local_fixes/sj077_2_ctx.changes.json --issue CTX-X1 --issue CTX-X2 \
 --operator-issue "sections.context.5|context review note (quote 侯生下見其客朱亥，俾倪故久立，與其客語，微察公子。公子顏色愈和): the friend is 朱亥; the waiting hall and the riders' curses show the weight of the test" \
 --reason "standing owner rule 2026-10-31: context-review findings with source quotes; zh fixed alongside en for parity"
echo "EXIT $?"

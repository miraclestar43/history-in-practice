#!/bin/bash
# Standing owner rule (2026-10-31): the rev3 context review's only blocker is its cut excerpt E29 (於是魏文侯以為將，擊秦，
# 拔五城), with a note that story.0 skips this direct result of 文侯's question. One recorded local fix adopting it; the
# last for rev3 -- anything new stays pending.
cd "$HOME/history-in-practice" || exit 1
systemd-run --user --wait --collect --pipe -q -p LimitAS=3G -p Nice=10 -p RuntimeMaxSec=3600 --working-directory="$HOME/history-in-practice" \
 bin/hip local-fix cand-auto-20261030-sj065-1 --changes data/local_fixes/wuqi_rev3_ctx.changes.json \
 --operator-issue "sections.story.0|context review note (quote 於是魏文侯以為將，擊秦，拔五城): the direct result of 文侯 asking 李克" \
 --reason "standing owner rule 2026-10-31: adopt the context review's cut excerpt E29 in the one sentence it concerns"
echo "EXIT $?"

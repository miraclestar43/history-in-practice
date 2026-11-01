#!/bin/bash
# Standing owner rule (2026-10-31): two open readability issues of rev3's final-editor record, each with a source quote
# (V2-V1: E12/E17, the two successive chief ministers; V2-V2: E21, who reformed Chu) -> one recorded local fix.
cd "$HOME/history-in-practice" || exit 1
systemd-run --user --wait --collect --pipe -q -p LimitAS=3G -p Nice=10 -p RuntimeMaxSec=3600 --working-directory="$HOME/history-in-practice" \
 bin/hip local-fix cand-auto-20261030-sj065-1 --changes data/local_fixes/wuqi_rev3_V2.changes.json --issue V2-V1 --issue V2-V2 \
 --reason "standing owner rule 2026-10-31: wording fixes with source quotes; tell the two chief ministers apart (田文 before 公叔) and name who reformed Chu"
echo "EXIT $?"

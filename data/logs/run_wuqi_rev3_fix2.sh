#!/bin/bash
# Standing owner rule (2026-10-31): three quote-backed issues raised by the verify pass after fix1 (all inherited from
# rev2): V3-V4 order of the three comparisons (source: 將三軍 / 治百官 / 守西河, checked in the cached text), V3-V1
# evidence tags (E20), V3-V8 attribution wording. Last local fix for rev3: anything new stays pending.
cd "$HOME/history-in-practice" || exit 1
systemd-run --user --wait --collect --pipe -q -p LimitAS=3G -p Nice=10 -p RuntimeMaxSec=3600 --working-directory="$HOME/history-in-practice" \
 bin/hip local-fix cand-auto-20261030-sj065-1 --changes data/local_fixes/wuqi_rev3_V3.changes.json --issue V3-V1 --issue V3-V4 --issue V3-V8 \
 --reason "standing owner rule 2026-10-31: source order of the three comparisons; E20 added to the hook's evidence; 李克 is not a participant"
echo "EXIT $?"

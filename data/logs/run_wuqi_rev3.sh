#!/bin/bash
# Owner request 2026-10-31: fix 吴起 by applying the new reader-first rules through the Claude final editor's actual
# prompts. Base = rev2 text unchanged (revision 3); one owner-authorized attempt + one context review (revise-base).
cd "$HOME/history-in-practice" || exit 1
systemd-run --user --wait --collect --pipe -q -p LimitAS=3G -p Nice=10 -p RuntimeMaxSec=7200 --working-directory="$HOME/history-in-practice" \
 bin/hip revise-base cand-auto-20261030-sj065-1 data/revisions/wuqi_rev3_base.json \
 --reason "owner request 2026-10-31 (prompt-level reader feedback): rev2 text unchanged as the base; the final editor applies prompts/reader_first_zh.md (same-title people, gradual introduction, dek/hook division, turning points) with its own audit/revise/verify"
echo "EXIT $?"

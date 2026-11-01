#!/bin/bash
# Owner request 2026-10-31: verify the reader-first rules transfer -- new Chinese story through the normal chain:
# prepare (Claude pre-draft context review + MiMo draft/review/English) -> MiMo editor -> Claude final editor
# (attempts + context review + admission, as for any new edition).
cd "$HOME/history-in-practice" || exit 1
R="systemd-run --user --wait --collect --pipe -q -p LimitAS=3G -p Nice=10 --working-directory=$HOME/history-in-practice"
$R .venv/bin/python data/logs/sj077_supersede.py release
$R -p RuntimeMaxSec=10800 bin/hip prepare config/candidates/auto-20261031-china_ancient-sj077-2.json; rc=$?
echo "PREPARE EXIT $rc"
if [ ! -f data/drafts/cand-auto-20261031-sj077-2/article.json ]; then
  $R .venv/bin/python data/logs/sj077_supersede.py restore; echo "EXIT prepare-failed"; exit 1
fi
$R .venv/bin/python data/logs/sj077_supersede.py retire
$R -p RuntimeMaxSec=10800 bin/hip edit cand-auto-20261031-sj077-2; echo "EDIT EXIT $?"
$R -p RuntimeMaxSec=14400 bin/hip final-edit cand-auto-20261031-sj077-2; echo "FINAL EXIT $?"
echo "EXIT done"

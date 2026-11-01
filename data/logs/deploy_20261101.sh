#!/bin/bash
# Deploy feature/book-supply (PR #4, merged) on raspberrypi51, 2026-11-01. Run by hand, once, outside the send
# (13:50-14:50 UTC) and nightly (01:50-04:45 UTC) windows. Timers, recipients, send time and the stored plan are untouched.
set -euo pipefail
P="$HOME/history-in-practice"; W="$HOME/hip-wt-books"; ADOPT="${ADOPT:?ids to adopt}"
hm=$((10#$(date -u +%H) * 60 + 10#$(date -u +%M)))
if (( (hm >= 110 && hm < 285) || (hm >= 830 && hm < 890) )); then echo "inside a production window; not now"; exit 3; fi
for u in hip-prepare.service hip-send.service; do systemctl --user is-active -q "$u" && { echo "$u running; not now"; exit 3; }; done
cd "$P"; git status --short --branch | head -3

echo "== 1. keep the book evidence packs that this merge stops tracking (they stay on the Pi)"
B="$P/data/backup-20261101-evidence"; mkdir -p "$B"
for f in samples/auto/cand-book-20261031-hushi-baihua/final/evidence.json samples/auto/cand-book-20261031-hushi-baihua/revisions/rev1/evidence.json \
         samples/auto/cand-book-20261031-curie-radium/final/evidence.json samples/auto/cand-book-20261031-curie-radium/final/context_evidence.json; do
  [ -f "$f" ] && { mkdir -p "$B/$(dirname "$f")"; cp -p "$f" "$B/$f"; }
done
(cd "$B" && find . -type f -exec sha256sum {} \;) > "$B.sha256"

echo "== 2. pull"
git pull --ff-only
git log -1 --oneline

echo "== 3. restore them as local (ignored) files"
(cd "$B" && find . -type f) | while read -r f; do [ -e "$P/$f" ] || { mkdir -p "$(dirname "$P/$f")"; cp -p "$B/$f" "$P/$f"; }; done
(cd "$P" && sha256sum -c <(sed "s#  \./#  #" "$B.sha256")) && git status --short | grep -c evidence || true

echo "== 4. library: fetch and ingest the selected books (resumable, blob verified)"
bin/hip library ingest --book all --max-new 10 | tee "$P/data/logs/library_sync_20261101.json" | grep -E '"book_id"|"outcome"' | paste - -

echo "== 5. local records of the articles finished in the worktree (evidence packs are not in Git)"
for id in $ADOPT; do mkdir -p "$P/samples/auto/$id"; cp -rn "$W/samples/auto/$id/." "$P/samples/auto/$id/"; done

echo "== 6. adopt through the unchanged admission"
bin/hip adopt $ADOPT

echo "== 7. reading layout on the live site (page shell only; edition data untouched)"
cp src/history_in_practice/templates/history_index.html data/website_prod/history/index.html
cd data/website_prod
if ! git diff --quiet -- history/index.html; then
  git add history/index.html && git commit -q -m "history: reading layout (type size, order, text size, folded notes; no internal ids)" && git push -q origin HEAD:main
fi
git log -1 --oneline
echo "DEPLOY DONE"

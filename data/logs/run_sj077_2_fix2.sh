#!/bin/bash
# Standing owner rule (2026-10-31; reader rule 7: key classical lines explained in plain Chinese in place): four quoted
# lines the final editor left unexplained in the Chinese (its attempt-3 note F4 named one); the English already renders
# them. Translation-only fix, zh only. Last local fix for sj077-2.
cd "$HOME/history-in-practice" || exit 1
systemd-run --user --wait --collect --pipe -q -p LimitAS=3G -p Nice=10 -p RuntimeMaxSec=3600 --working-directory="$HOME/history-in-practice" \
 bin/hip local-fix cand-auto-20261031-sj077-2 --changes data/local_fixes/sj077_2_classical.changes.json \
 --operator-issue "sections.story.0|reader rule 7: 「此五霸之伐也」 quoted without a plain gloss (English: an achievement worthy of the Five Hegemons)" \
 --operator-issue "sections.story.3|reader rule 7 / final-editor note attempt-3 F4: 「嚄唶宿將」 quoted without a plain gloss (English renders it)" \
 --operator-issue "sections.story.7|reader rule 7: 「意驕矜而有自功之色」「立自責，似若無所容者」 quoted without a plain gloss" \
 --reason "standing owner rule 2026-10-31: translation fixes with a clear source basis; key classical lines glossed in place"
echo "EXIT $?"

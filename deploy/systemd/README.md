# systemd user units: 没事儿多读书 (live since 2026-11-01)

**Installed and enabled on raspberrypi51** as user `star` (uid 1000). The unit files in this directory are linked into `~/.config/systemd/user/`. Launch record, rollback and checks: `docs/LAUNCH_20261101.md`.

| Unit | When (Asia/Shanghai) | What |
|---|---|---|
| `hip-send.timer` → `hip-send.service` | daily **22:08** (= 06:08 PST / 07:08 PDT) | `recover`, then publish today's issue: site commit → push → live check → email |
| `hip-send-retry.timer` → `hip-send.service` | 22:38, 23:08, 23:35; 23:45 | resumes a run whose deploy is still landing or whose send partly failed (idempotent). The 23:45 run marks an unfinished day `overdue` and alerts |
| `hip-prepare.timer` → `hip-prepare.service` | daily **10:00** | `hip nightly`: candidate top-up → Claude drafting → final editor (batch budget) |

**Both services** run `hip alert` in `ExecStopPost`: one email to the maintainer, never to subscribers, once per problem per day.

**Claude** (Claude Code CLI, claude.ai subscription) drafts, writes the English and edits. There is no other model and no fallback: if Claude is unavailable, the run exits 4 and alerts.

## Reboot recovery (no login, no SSH, no Claude session needed)

**Lingering.** `loginctl show-user star -p Linger` → `Linger=yes`. The user manager (`user@1000.service`) starts at boot and starts the enabled timers. If lingering were ever off, restore it with `loginctl enable-linger star`.

**Timers.** All three are `enabled` in `timers.target.wants`, so they come back after every boot. Verified after the reboot of 2026-11-01 01:32 CT: active since boot, nothing run.

**No catch-up, no early send, no late send:**
- every timer has `Persistent=false`, so a boot never triggers a missed run;
- `publish-today` starts nothing before 22:08 Beijing time and sends nothing after the 23:40 deadline or on a later day;
- per-recipient delivery records make a rerun resend nothing.

**Everything is readable without a session, using files under `/home/star` only:**
- code and venv: `~/history-in-practice` (branch `main`); `bin/hip` uses absolute paths;
- private runtime config `~/.config/history-in-practice/runtime.env` (0600): SMTP, recipients, site push and send flags;
- the Claude login: `~/.config/history-in-practice/claude/.credentials.json` (0600; a file, not a keyring);
- GitHub push for the site: `gh` credential helper, token in `~/.config/gh/hosts.yml` (0600; a file, not a keyring);
- production website copy: `data/website_prod` (`main` of `website_test`).

`hip doctor` and a push dry-run were checked from inside the user manager (`systemd-run --user`, no SSH environment): runtime config, email config, Claude preflight and push all OK.

**After a reboot, check:**
```
loginctl show-user star -p Linger
systemctl --user list-timers 'hip-*'
systemctl --user --failed
bin/hip status
```

**Stop or roll back:**
- `systemctl --user disable --now hip-send.timer hip-send-retry.timer hip-prepare.timer`;
- `EMAIL_SEND_ENABLED=false` in the runtime config.

**Logs** append to `data/logs/` (`send.log`, `prepare.log`). Log rotation is still to be added.

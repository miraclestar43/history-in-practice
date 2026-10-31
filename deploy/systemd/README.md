**Status 2026-10-30 (AFK test):** no unit is installed or enabled. A successful TEST email/website is not authorization to enable timers or recurring sends; that remains an owner decision. The prepare unit now runs MiMo drafting + the Pi-local Claude final editor (`hip nightly`, exit 4 = final editor unavailable).

# systemd templates (NOT enabled)

User units for raspberrypi51. Nothing here is installed by the repo, and no timer has been enabled.

| Unit | When | What |
|---|---|---|
| `hip-prepare.service/.timer` | 20:00 America/Los_Angeles | `hip nightly`: candidate top-up from the source catalogue → pipeline → editor stage (batch budget) |
| `hip-send.service/.timer` | 07:30 America/Los_Angeles | `recover`, then publish today's edition (site → bounded live wait → email) |
| `hip-send-retry.timer` | 08:00–10:30 every 30 min, America/Los_Angeles | reruns `hip-send.service` while a deploy is still landing or a send partly failed; idempotent |

Before enabling:

1. Fill the private runtime env (`~/.config/history-in-practice/runtime.env`, mode 600): Resend key, From, **Reply-To (required: the footer asks readers to reply and the From address has no mailbox)**. Run the one-off tracked test `bin/hip test-edition send --test-id ID --confirm-real-email` (works while `EMAIL_SEND_ENABLED=false`; see docs/EMAIL_SETUP.md), check both inboxes and reply once; only then set `EMAIL_SEND_ENABLED=true`.
2. Confirm the Cloudflare deployment path for the website repo.
3. `mkdir -p data/logs`, then `systemctl --user link $PWD/deploy/systemd/hip-*.{service,timer}`.
4. Check `systemd-analyze calendar "*-*-* 07:30:00 America/Los_Angeles"`, then `systemctl --user enable --now hip-prepare.timer hip-send.timer hip-send-retry.timer`.
5. `bin/hip inventory` must show `coverage_days` ≥ 7 before enabling sends; samples count only after `hip approve-sample`.

Logs append to `data/logs/`. Log rotation (`logrotate` or a size check in `hip doctor`) is still to be added. Restarting is safe: `recover` turns interrupted sends into `unknown`, which are never resent automatically.

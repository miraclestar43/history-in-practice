# systemd templates (NOT enabled)

User units for raspberrypi51. Nothing here is installed by the repo, and no timer has been enabled.

| Unit | When | What |
|---|---|---|
| `hip-prepare.service/.timer` | 20:00 America/Los_Angeles | Batch inventory build (multi-article budget, not a per-article timeout) |
| `hip-send.service/.timer` | 07:30 America/Los_Angeles | `recover`, then publish today's scheduled edition (site → live check → email) |

Before enabling:

1. Fill the private runtime env (`~/.config/history-in-practice/runtime.env`, mode 600) with the Resend key, and set `EMAIL_SEND_ENABLED=true` only after a real test send.
2. Confirm the Cloudflare deployment path for the website repo.
3. `mkdir -p data/logs`, then `systemctl --user link $PWD/deploy/systemd/hip-*.{service,timer}`.
4. Check `systemd-analyze calendar "*-*-* 07:30:00 America/Los_Angeles"`, then `systemctl --user enable --now hip-prepare.timer hip-send.timer`.

Logs append to `data/logs/`. Log rotation (`logrotate` or a size check in `hip doctor`) is still to be added. Restarting is safe: `recover` turns interrupted sends into `unknown`, which are never resent automatically.

"""Maintainer alerts for the daily jobs (launch 2026-11-01).

Each scheduled job records how it ended under data/health/ (publish_last.json, final_editor.json, nightly_last.json).
`hip alert` (ExecStopPost of hip-send.service and hip-prepare.service, so it runs whatever the exit code) turns the states
that need a person into ONE plain-text email to the maintainer -- ALERT_EMAIL in the private runtime env, else
EMAIL_REPLY_TO (the owner's mailbox) -- never to subscribers. The same problem alerts once per Los Angeles day.

Alerted: no eligible edition (skipped); overdue (not sent, never sent late); a partial send; a run still waiting at the
last retry before the deadline; Claude unavailable or degraded (drafting/final editing paused, no other model is used);
the Claude login close to expiry; inventory below the alert line. Not alerted: an ordinary wait while a deploy lands.
"""
from __future__ import annotations
import hashlib, json, time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from pathlib import Path
from .config import data_dir


def _read(name: str) -> dict | None:
    p = data_dir() / "health" / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def record(name: str, obj: dict):
    p = data_dir() / "health" / name; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(obj, recorded_at=time.time()), ensure_ascii=False, indent=1), encoding="utf-8")


def problems(now_la, deadline_s_left: float | None = None) -> list[str]:
    """What needs a person, from the jobs' last records of today (LA)."""
    out, today = [], now_la.date().isoformat()
    pub = _read("publish_last.json")
    if pub and pub.get("date") == today:
        o, why = pub.get("outcome"), str(pub.get("reason") or "")[:300]
        if o == "skipped":
            out.append(f"今日未发送（无合格稿件）：{why}")
        elif o == "overdue":
            out.append(f"今日一期逾期，未发送，也不会补发：{why}")
        elif o == "partial":
            out.append(f"今日一期只发出一部分（逐收件人记录在案，不会重复发送）：{why}")
        elif o == "waiting" and deadline_s_left is not None and deadline_s_left < 45 * 60:
            out.append(f"临近截止仍在等待：{why}")
        if pub.get("overdue"):
            out.append("此前未完成的期次已标为逾期（不补发）：" + "; ".join(pub["overdue"])[:300])
    fe = _read("final_editor.json")
    if fe and fe.get("final_editor") != "ok" and fe.get("checked_at", 0) > time.time() - 36 * 3600:
        out.append("Claude 不可用，起稿与终审已暂停（不会改用其他模型）：" + "; ".join(fe.get("problems") or [])[:300])
    for w in (fe or {}).get("warnings") or []:
        out.append(w)
    ni = _read("nightly_last.json")
    if ni and ni.get("recorded_at", 0) > time.time() - 36 * 3600:
        if ni.get("writer_unavailable"):
            out.append("夜间起稿未运行：" + str(ni["writer_unavailable"])[:300])
        if ni.get("inventory_alert"):
            out.append(f"可排库存低于告警线：{ni.get('coverage_days')} 天")
    return out


def send(runtime, subject: str, body: str, send_one=None) -> tuple[str, str]:
    from . import mailer
    send_one = send_one or mailer.send_one
    to = runtime.get("ALERT_EMAIL") or parseaddr(runtime.get("EMAIL_REPLY_TO"))[1]
    if not to:
        return "failed", "no ALERT_EMAIL or EMAIL_REPLY_TO configured"
    m = EmailMessage()
    m["From"] = runtime.get("EMAIL_FROM"); m["To"] = to; m["Subject"] = subject
    m["Date"] = formatdate(localtime=False); m["Message-ID"] = make_msgid(domain="read.starhub.vip")
    m.set_content(body, charset="utf-8")
    cfg = {"host": runtime.get("SMTP_HOST"), "port": runtime.get("SMTP_PORT", "465"), "security": runtime.get("SMTP_SECURITY", "ssl"),
           "username": runtime.get("SMTP_USERNAME"), "password": runtime.get("SMTP_PASSWORD")}
    return send_one(cfg, m, to)


def run(runtime, now_la, *, source: str, deadline_s_left: float | None = None, dry_run: bool = False, send_one=None) -> dict:
    ps = problems(now_la, deadline_s_left)
    if not ps:
        return {"alert": "none"}
    fp = hashlib.sha256("\n".join(ps).encode()).hexdigest()[:16]
    seen = _read("alert_last.json") or {}
    key = f"{now_la.date().isoformat()}:{fp}"
    if key in (seen.get("sent") or []):
        return {"alert": "already sent today", "problems": ps}
    body = ("没事儿多读书 · 维护提醒（" + now_la.strftime("%Y-%m-%d %H:%M") + " 洛杉矶时间，来自 " + source + "）\n\n"
            + "\n".join(f"- {p}" for p in ps) + "\n\n查看：bin/hip status ；日志：data/logs/。本邮件只发给维护者。")
    if dry_run:
        return {"alert": "dry run", "problems": ps, "body": body}
    status, detail = send(runtime, f"没事儿多读书 · 需要处理（{now_la.strftime('%m-%d')}）", body, send_one=send_one)
    if status == "accepted":
        sent = (seen.get("sent") or [])[-30:] + [key]
        record("alert_last.json", {"sent": sent})
    return {"alert": status, "detail": detail, "problems": ps}

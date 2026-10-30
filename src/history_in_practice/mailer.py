"""One SMTP sender (Resend-compatible SMTPS or STARTTLS), per-recipient state.

Safety:
* Real network sending requires EMAIL_SEND_ENABLED=true in the private
  runtime env. Tests use ``mode="local-test"``, which only connects to
  127.0.0.1/::1 and never reads real recipients.
* Each recipient is sent separately. Envelope errors (MAIL/RCPT refused,
  connect/login failure) -> ``failed`` (safe to retry). Any error after the
  DATA phase has started -> ``unknown`` (never auto-retried: the server may
  already have accepted it). 2xx after DATA -> ``accepted`` (SMTP accepted,
  NOT "delivered to inbox").
* Message-ID is stable per (edition, revision, recipient) so a manual resend
  after an `unknown` can be recognised as a duplicate by the reader's client.
"""
from __future__ import annotations
import hashlib, smtplib, socket, ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr, formatdate
from email.header import Header
from . import state

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


class SendDisabled(RuntimeError):
    pass


def message_id(edition_id: str, revision: int, rkey: str, domain: str) -> str:
    h = hashlib.sha256(f"{edition_id}|{revision}|{rkey}".encode()).hexdigest()[:20]
    return f"<hip.{edition_id}.r{revision}.{h}@{domain}>"


def build_message(obj: dict, html: str, text: str, sender: str, to: str, msg_id: str, reply_to: str = "") -> EmailMessage:
    m = EmailMessage()
    name, addr = parseaddr(sender)
    m["From"] = formataddr((str(Header(name, "utf-8")), addr)) if name else addr
    m["To"] = to
    if reply_to:
        m["Reply-To"] = reply_to
    num = obj.get("edition_number")
    prefix = f"每日一鉴 #{num:03d}｜" if isinstance(num, int) else "每日一鉴｜"
    m["Subject"] = prefix + obj["title"]["zh"]
    m["Message-ID"] = msg_id
    m["Date"] = formatdate(localtime=False)
    m["X-HIP-Edition"] = f"{obj['edition_id']} r{obj['revision']} {obj.get('content_sha256', '')[:12]}"
    m.set_content(text, charset="utf-8")
    m.add_alternative(html, subtype="html", charset="utf-8")
    return m


def _connect(cfg, timeout):
    host, port, sec = cfg["host"], int(cfg["port"]), cfg.get("security", "ssl")
    ctx = cfg.get("ssl_context") or ssl.create_default_context()
    if sec == "ssl":
        s = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx)
    else:
        s = smtplib.SMTP(host, port, timeout=timeout)
        s.ehlo()
        if sec == "starttls":
            s.starttls(context=ctx); s.ehlo()
    if cfg.get("username"):
        s.login(cfg["username"], cfg["password"])
    return s


def send_one(cfg, msg: EmailMessage, rcpt: str, timeout=30) -> tuple[str, str]:
    """Returns (status, detail) with status in accepted|failed|unknown."""
    try:
        s = _connect(cfg, timeout)
    except (OSError, smtplib.SMTPException) as e:
        return "failed", f"connect/login: {type(e).__name__}"
    try:
        sender = parseaddr(msg["From"])[1]
        code, resp = s.mail(sender)
        if code != 250:
            return "failed", f"MAIL {code}"
        code, resp = s.rcpt(rcpt)
        if code not in (250, 251):
            return "failed", f"RCPT {code}"
    except (OSError, smtplib.SMTPException) as e:
        _quiet_close(s)
        return "failed", f"envelope: {type(e).__name__}"
    try:
        code, resp = s.data(msg.as_bytes())
    except smtplib.SMTPDataError as e:          # server answered with an error code
        _quiet_close(s)
        return ("failed" if 400 <= e.smtp_code < 600 else "unknown"), f"DATA {e.smtp_code}"
    except (OSError, smtplib.SMTPException, socket.timeout) as e:  # outcome not known
        _quiet_close(s)
        return "unknown", f"during DATA: {type(e).__name__}"
    _quiet_close(s)
    return ("accepted", "250") if code == 250 else ("unknown", f"DATA {code}")


def _quiet_close(s):
    try:
        s.quit()
    except Exception:
        try: s.close()
        except Exception: pass


def send_edition(db, obj, html, text, runtime, *, mode="real", smtp_cfg=None, recipients=None, domain="read.starhub.vip") -> list[dict]:
    """Send one edition to each recipient once. Returns a report without addresses."""
    if mode == "real":
        if not runtime.send_enabled:
            raise SendDisabled("EMAIL_SEND_ENABLED is not true; refusing to send")
        rcpts = runtime.recipients
        cfg = {"host": runtime.get("SMTP_HOST"), "port": runtime.get("SMTP_PORT", "465"), "security": runtime.get("SMTP_SECURITY", "ssl"),
               "username": runtime.get("SMTP_USERNAME"), "password": runtime.get("SMTP_PASSWORD")}
        sender, reply_to = runtime.get("EMAIL_FROM"), runtime.get("EMAIL_REPLY_TO")
    elif mode == "local-test":
        if not smtp_cfg or smtp_cfg["host"] not in LOCAL_HOSTS:
            raise SendDisabled("local-test mode only connects to localhost")
        rcpts, cfg, sender, reply_to = list(recipients or []), smtp_cfg, smtp_cfg.get("from", "test@example.invalid"), ""
    else:
        raise ValueError(mode)
    rev = obj["revision"]; eid = obj["edition_id"]; report = []
    for r in rcpts:
        key, label = state.recipient_key(r), state.recipient_label(r)
        st, attempts = state.delivery_status(db, eid, rev, key)
        if st in ("accepted", "unknown", "sending"):
            report.append({"recipient": label, "status": st, "action": "skipped (already " + st + ")"}); continue
        mid = message_id(eid, rev, key, domain)
        state.set_delivery(db, eid, rev, key, label, "sending", message_id=mid, bump=True)
        status, detail = send_one(cfg, build_message(obj, html, text, sender, r, mid, reply_to), r)
        state.set_delivery(db, eid, rev, key, label, status, error=None if status == "accepted" else detail)
        report.append({"recipient": label, "status": status, "detail": detail})
    return report

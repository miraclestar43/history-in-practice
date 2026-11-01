"""Build ONE offline preview of the reading email with the news digest at its end (2026-11-01; replaces the
prompts/08 news-first preview): an admitted story + news-intel's frozen brief for one Beijing edition date.

Usage: .venv/bin/python validation/combined_preview.py EDITION --news-export DIR --date YYYY-MM-DD --out DIR [--now ISO]
Writes <out>/<name>.email.html, .email.txt, .eml (to a fictional recipient, to measure the real size) and the
news archive page the digest links to. Nothing is sent, published or bound: the binding is a preview
(news.bind(persist=False)), so the scheduled send later freezes its own.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import final_edit, mailer, news, render, state  # noqa: E402
from history_in_practice.cli import db  # noqa: E402
from history_in_practice.config import data_dir  # noqa: E402

FICTIONAL = "Reader One <reader.one@example.invalid>"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("edition"); ap.add_argument("--news-export", required=True)
    ap.add_argument("--date", required=True); ap.add_argument("--out", required=True); ap.add_argument("--now")
    ap.add_argument("--base", default="https://starhub.vip")
    a = ap.parse_args()
    problems, o = final_edit.current_eligibility(db(), a.edition)
    if problems or o is None:
        raise SystemExit(f"story not admitted now: {problems}")
    o = json.loads(json.dumps(o)); o["edition_date"] = a.date               # preview date = the news edition date
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    nb = news.bind(data_dir() / "news_bindings", o, Path(a.news_export), a.base, now, persist=False)
    html = render.email_html(o, a.base, news=nb); text = render.email_text(o, a.base, news=nb)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); name = f"{a.date}-{o['edition_id']}"
    (out / f"{name}.email.html").write_text(html, encoding="utf-8"); (out / f"{name}.email.txt").write_text(text, encoding="utf-8")
    for rel, page in news.site_files(nb).items():
        (out / f"{name}.news-archive.html").write_text(page, encoding="utf-8")
    m = mailer.build_message(o, html, text, "没事儿多读书 <history@read.starhub.vip>", FICTIONAL,
                             mailer.message_id(o["edition_id"], o["revision"], state.recipient_key(FICTIONAL), "read.starhub.vip"))
    eml = out / f"{name}.eml"; eml.write_bytes(bytes(m))
    print(json.dumps({"news": {k: nb.get(k) for k in ("status", "snapshot_id", "text_sha256", "reason", "items")},
                      "digest_zh_chars": (nb.get("digest") or {}).get("zh_chars"), "story_minutes": o["reading_minutes"],
                      "html_bytes": len(html.encode()), "text_bytes": len(text.encode()), "eml_bytes": eml.stat().st_size,
                      "gmail_clip_limit_bytes": 102 * 1024, "out": str(out)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

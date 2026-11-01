"""Build ONE combined reading preview (prompts/08 §6): the 3-minute news snapshot + an admitted story, as
1. a static web page under the TEST preview site (history/preview/<name>.html; only history/ paths are written), and
2. an .eml addressed to a fictional recipient, to measure the real message size. Nothing is sent.

Usage: .venv/bin/python validation/combined_preview.py EDITION NEWS.json --site-root DIR --name NAME [--now ISO]
The story must be admitted now (final_edit.current_eligibility); the news snapshot must pass render.news_problems()
or the preview shows the honest "暂缺" note instead.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from history_in_practice import final_edit, render, mailer, site_export, state  # noqa: E402
from history_in_practice.cli import db  # noqa: E402

FICTIONAL = "Reader One <reader.one@example.invalid>"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("edition"); ap.add_argument("news"); ap.add_argument("--site-root", required=True)
    ap.add_argument("--name", required=True); ap.add_argument("--now"); ap.add_argument("--out", default="data/preview")
    a = ap.parse_args()
    problems, o = final_edit.current_eligibility(db(), a.edition)
    if problems or o is None:
        raise SystemExit(f"story not admitted now: {problems}")
    news = json.loads(Path(a.news).read_text(encoding="utf-8")); nprob = render.news_problems(news, a.now)
    o = json.loads(json.dumps(o)); o["edition_date"] = news["intended_edition_date"]      # preview date = the news date
    base = "https://hip-test-20261030.website-test-7i3.pages.dev"
    html = render.email_html(o, base, news=news, now_iso=a.now); text = render.email_text(o, base, news=news, now_iso=a.now)
    page = site_export._safe_dest(Path(a.site_root), f"history/preview/{a.name}.html"); page.parent.mkdir(parents=True, exist_ok=True)
    banner = ('<p style="font-family:sans-serif;font-size:14px;margin:0;padding:10px 14px;background:#fff3e8;color:#7a2e12;'
              'border-bottom:2px solid #b5542f;">测试预览 · 组合版式样稿（新闻＋故事），没有发送给任何人。TEST preview of the combined '
              'format; not sent to anyone.</p>')
    page.write_text(html.replace("<body style=\"margin:0;padding:0;background:#faf8f4;\">",
                                 "<body style=\"margin:0;padding:0;background:#faf8f4;\">" + banner, 1), encoding="utf-8")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    m = mailer.build_message(o, html, text, "没事儿多读书 <history@read.starhub.vip>", FICTIONAL,
                             mailer.message_id(o["edition_id"], o["revision"], state.recipient_key(FICTIONAL), "read.starhub.vip"))
    eml = out / f"{a.name}.eml"; eml.write_bytes(bytes(m))
    print(json.dumps({"page": str(page), "eml": str(eml), "news_problems": nprob, "news_minutes": render.news_minutes(news),
                      "story_minutes": o["reading_minutes"], "html_bytes": len(html.encode()), "text_bytes": len(text.encode()),
                      "eml_bytes": eml.stat().st_size, "gmail_clip_limit_bytes": 102 * 1024}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

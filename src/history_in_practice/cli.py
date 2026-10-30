"""hip — History in Practice command line.

  hip doctor                         environment, isolation probe, config (no secret values)
  hip prepare CANDIDATE.json [--mock-llm]
  hip check ARTICLE.json EVIDENCE.json
  hip render ARTICLE.json... --out DIR        email html/txt/.eml (fictional To), site data, markdown
  hip export-site ARTICLE.json... --site-root DIR
  hip verify-site ARTICLE.json --base-url URL
  hip send ARTICLE.json --dry-run | --local-smtp HOST:PORT [--recipients-file F] | --real
  hip status | hip inventory | hip recover
  hip retry-send ARTICLE.json --real|--local-smtp HOST:PORT   (retries `failed` only, never `unknown`)
  hip registry-rebuild CONTENT.json...
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path
from . import config, state, registry, checks, render, pipeline, site_export, mailer, llm
from .config import REPO, data_dir


def db():
    d = state.connect(data_dir() / "hip.sqlite"); registry.init(d, _aliases())
    return d


def _aliases():
    p = REPO / "config/aliases.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def cmd_doctor(a):
    out = {"python": sys.version.split()[0]}
    from .textnorm import HAVE_OPENCC
    out["opencc"] = HAVE_OPENCC
    out["hermes_python"] = os.path.exists(llm.HERMES_PY)
    rt = config.load_runtime()
    out["runtime_env"] = {"path_exists": bool(rt.path and rt.path.exists()), "insecure_permissions": rt.insecure_permissions,
                          "keys": rt.describe(), "send_enabled": rt.send_enabled}
    if a.probe and out["hermes_python"]:
        probe = REPO / "validation/hermes_probe.py"
        with __import__("tempfile").TemporaryDirectory() as wd:
            r = subprocess.run([llm.HERMES_PY, str(probe), "direct", "[]"], capture_output=True, text=True, timeout=180, cwd=wd)
        try:
            p = json.loads(r.stdout.strip().splitlines()[-1])
            out["isolation_probe"] = {k: p[k] for k in ("tool_count", "cwd_canary_in_prompt", "soul_text_in_prompt", "memory_store_loaded")}
            out["isolation_ok"] = p["tool_count"] == 0 and not p["soul_text_in_prompt"] and not p["memory_store_loaded"]
        except Exception as e:
            out["isolation_probe"] = f"failed: {type(e).__name__}"; out["isolation_ok"] = False
    d = db(); out["state"] = state.summary(d); out["inventory"] = pipeline.inventory(d)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out.get("isolation_ok", True) and out["opencc"] else 1


def _mock_call(prompt, timeout_s=0, **_):
    raise SystemExit("--mock-llm needs a fixture; see tests/test_pipeline.py")


def cmd_prepare(a):
    c = pipeline.load_candidate(a.candidate)
    rep = pipeline.prepare(c, db())
    print(json.dumps({k: v for k, v in rep.items() if k != "findings"} | {"findings": rep.get("findings", [])[:20]}, ensure_ascii=False, indent=1))
    return 0 if rep.get("outcome") == "checked" else 2


def cmd_check(a):
    f, st = checks.check(_load(a.article), _load(a.evidence))
    print(json.dumps({"stats": st, "findings": f, "blocked": checks.blocked(f)}, ensure_ascii=False, indent=1))
    return 1 if checks.blocked(f) else 0


FICTIONAL = ["reader1@example.invalid", "reader2@example.invalid"]


def cmd_render(a):
    objs = [_load(p) for p in a.articles]; out = Path(a.out)
    render.build(objs, out, a.base_url)
    for o in objs:
        html = (out / "email" / f"{o['edition_id']}.html").read_text(encoding="utf-8")
        text = (out / "email" / f"{o['edition_id']}.txt").read_text(encoding="utf-8")
        for i, r in enumerate(FICTIONAL):
            m = mailer.build_message(o, html, text, "每日一鉴 <history@read.starhub.vip>", r,
                                     mailer.message_id(o["edition_id"], o["revision"], state.recipient_key(r), "read.starhub.vip"))
            (out / "email" / f"{o['edition_id']}.reader{i+1}.eml").write_bytes(bytes(m))
        print(json.dumps({"edition": o["edition_id"], "html_bytes": len(html.encode()), "text_bytes": len(text.encode()),
                          "content_sha256": o["content_sha256"][:16], "reading_minutes": o["reading_minutes"]}, ensure_ascii=False))
    return 0


def cmd_export_site(a):
    written = site_export.export([_load(p) for p in a.articles], Path(a.site_root))
    print(json.dumps({"written": written}, ensure_ascii=False, indent=1)); return 0


def cmd_verify_site(a):
    ok, problems = site_export.verify(_load(a.article), a.base_url)
    print(json.dumps({"ok": ok, "problems": problems}, ensure_ascii=False, indent=1)); return 0 if ok else 1


def _send(a, retry=False):
    o = _load(a.article); d = db()
    out = Path(a.out) if getattr(a, "out", None) else data_dir() / "outbox"
    render.build([dict(o)], out, a.base_url)
    html = (out / "email" / f"{o['edition_id']}.html").read_text(encoding="utf-8")
    text = (out / "email" / f"{o['edition_id']}.txt").read_text(encoding="utf-8")
    if a.dry_run:
        print(json.dumps({"dry_run": True, "html_bytes": len(html.encode()), "note": "nothing sent; see `hip render` for .eml"}, ensure_ascii=False)); return 0
    if retry:
        for k, in d.execute("SELECT recipient_key FROM delivery WHERE edition_id=? AND revision=? AND status='failed'", (o["edition_id"], o["revision"])):
            state.set_delivery(d, o["edition_id"], o["revision"], k, None, "pending")
    if a.local_smtp:
        host, port = a.local_smtp.rsplit(":", 1)
        rcpts = Path(a.recipients_file).read_text().split() if a.recipients_file else FICTIONAL
        cfg = {"host": host, "port": port, "security": a.security, "username": "", "password": "", "from": "history@read.starhub.vip"}
        if a.security != "plain":
            import ssl; ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE; cfg["ssl_context"] = ctx
        rep = mailer.send_edition(d, o, html, text, None, mode="local-test", smtp_cfg=cfg, recipients=rcpts)
    elif a.real:
        rep = mailer.send_edition(d, o, html, text, config.load_runtime(), mode="real")
    else:
        raise SystemExit("choose --dry-run, --local-smtp HOST:PORT or --real")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if all(r["status"] in ("accepted",) or r.get("action", "").startswith("skipped") for r in rep) else 3


def cmd_status(a):
    d = db(); s = state.summary(d)
    s["recent"] = [dict(zip(("edition_id", "status", "category", "reason"), r)) for r in
                   d.execute("SELECT edition_id,status,category,substr(COALESCE(reason,''),1,160) FROM edition ORDER BY updated_at DESC LIMIT 15")]
    s["deliveries"] = [dict(zip(("edition", "rev", "recipient", "status", "attempts", "error"), r)) for r in
                       d.execute("SELECT edition_id,revision,recipient_label,status,attempts,last_error FROM delivery ORDER BY updated_at DESC LIMIT 20")]
    print(json.dumps(s, ensure_ascii=False, indent=1)); return 0


def cmd_inventory(a):
    inv = pipeline.inventory(db()); print(json.dumps(inv, ensure_ascii=False, indent=1)); return 1 if inv["alert"] else 0


def cmd_recover(a):
    print(json.dumps({"marked_unknown": state.recover(db())}, ensure_ascii=False)); return 0


def cmd_registry_rebuild(a):
    d = state.connect(Path(a.db)) if a.db else db(); registry.init(d, _aliases())
    n = registry.rebuild_from_content(d, [Path(p) for p in a.content])
    print(json.dumps({"episodes_registered": n}, ensure_ascii=False)); return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hip", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("doctor"); p.add_argument("--probe", action="store_true"); p.set_defaults(f=cmd_doctor)
    p = sp.add_parser("prepare"); p.add_argument("candidate"); p.set_defaults(f=cmd_prepare)
    p = sp.add_parser("check"); p.add_argument("article"); p.add_argument("evidence"); p.set_defaults(f=cmd_check)
    p = sp.add_parser("render"); p.add_argument("articles", nargs="+"); p.add_argument("--out", required=True)
    p.add_argument("--base-url", default="https://starhub.vip"); p.set_defaults(f=cmd_render)
    p = sp.add_parser("export-site"); p.add_argument("articles", nargs="+"); p.add_argument("--site-root", required=True); p.set_defaults(f=cmd_export_site)
    p = sp.add_parser("verify-site"); p.add_argument("article"); p.add_argument("--base-url", required=True); p.set_defaults(f=cmd_verify_site)
    for name, retry in (("send", False), ("retry-send", True)):
        p = sp.add_parser(name); p.add_argument("article"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--real", action="store_true")
        p.add_argument("--local-smtp"); p.add_argument("--security", default="ssl", choices=["ssl", "starttls", "plain"])
        p.add_argument("--recipients-file"); p.add_argument("--out"); p.add_argument("--base-url", default="https://starhub.vip")
        p.set_defaults(f=(lambda a, r=retry: _send(a, r)))
    for name, f in (("status", cmd_status), ("inventory", cmd_inventory), ("recover", cmd_recover)):
        sp.add_parser(name).set_defaults(f=f)
    p = sp.add_parser("registry-rebuild"); p.add_argument("content", nargs="+"); p.add_argument("--db"); p.set_defaults(f=cmd_registry_rebuild)
    a = ap.parse_args(argv)
    state.recover(db()) if a.cmd not in ("doctor",) else None
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())

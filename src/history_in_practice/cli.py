"""hip — History in Practice command line.

  hip doctor                         environment, isolation probe, config (no secret values)
  hip prepare CANDIDATE.json
  hip check ARTICLE.json EVIDENCE.json
  hip render ARTICLE.json... --out DIR        email html/txt/.eml (fictional To), site data, markdown
  hip export-site ARTICLE.json... --site-root DIR
  hip verify-site ARTICLE.json --base-url URL
  hip send ARTICLE.json --dry-run | --local-smtp HOST:PORT [--recipients-file F] | --real
  hip send-test ARTICLE.json --confirm-real-email   one-off REAL test to the configured recipients (works while
                                                   EMAIL_SEND_ENABLED=false; full config required; separate test edition id)
  hip supply [--category C] [--max N] | --check    catalogue -> model proposal -> anchors verified -> new candidate file
  hip prepare-queue [--max-articles N --budget-minutes M]   (config/candidates/*.json, file lock)
  hip edit EDITION | hip edit-queue [--max N]       editor stage: bounded edit rounds -> re-review + English parity -> admit or stay pending
  hip rereview EDITION [--article FILE]             bind a fresh review + parity check to an edition's current (or given) content
  hip nightly                                       supply (if few candidates) -> prepare-queue -> edit-queue, one batch budget
  hip publish-today [--date YYYY-MM-DD]             (schedule -> archive -> site -> bounded live wait -> email); exit 0 complete,
                                                   3 partial, 4 skipped, 5 waiting, 6 overdue
  hip status | hip inventory | hip recover
  hip retry-send ARTICLE.json --real|--local-smtp HOST:PORT   (retries `failed` only, never `unknown`)
  hip requeue EDITION --reason TEXT        (checked -> pending, e.g. after a stricter rule)
  hip final-edit EDITION [EDITION ...]     named final editor (Pi-local Claude Code CLI, subscription); admits only via a verified record
  hip admit ARTICLE.json EVIDENCE.json --record RECORD.json [--exception ISSUE_ID=REASON ...]
                                           (record must match the article and evidence; each open FIX needs its own named reason;
                                            final-editor records accept no exceptions)
  hip admit ARTICLE.json EVIDENCE.json --as-sample   (register a sample: never schedulable until `hip approve-sample`)
  hip approve-sample EDITION --reason TEXT
  hip registry-rebuild CONTENT.json...
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path
import shutil
from . import config, state, registry, checks, render, pipeline, site_export, mailer, llm, publish, editor, supply
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
    logs = data_dir() / "logs"; size = sum(f.stat().st_size for f in logs.rglob("*") if f.is_file()) if logs.exists() else 0
    cache = data_dir() / "source_cache"; csize = sum(f.stat().st_size for f in cache.rglob("*") if f.is_file()) if cache.exists() else 0
    out["disk"] = {"logs_mb": round(size / 1e6, 1), "source_cache_mb": round(csize / 1e6, 1),
                   "warnings": [w for w, bad in (("logs over 200 MB: rotate", size > 200e6), ("source cache over 2 GB: prune", csize > 2e9)) if bad]}
    out["email_config_problems"] = mailer.validate_config(rt)
    d = db(); out["state"] = state.summary(d); out["inventory"] = pipeline.inventory(d)
    out["alerts"] = ([f"{n} overdue edition(s): not sent late; check `hip status`" for n in [d.execute("SELECT count(*) FROM edition WHERE status='overdue'").fetchone()[0]] if n]
                     + (["inventory coverage below alert threshold"] if out["inventory"]["alert"] else []))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out.get("isolation_ok", True) and out["opencc"] else 1


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
        try:
            rep = mailer.send_edition(d, o, html, text, config.load_runtime(), mode="real")
        except (mailer.SendDisabled, mailer.ConfigIncomplete) as e:
            print(json.dumps({"sent": False, "reason": str(e)}, ensure_ascii=False)); return 2
    else:
        raise SystemExit("choose --dry-run, --local-smtp HOST:PORT or --real")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if state.delivery_complete(d, o["edition_id"], o["revision"]) else 3   # every frozen recipient accepted, or attention needed


def cmd_send_test(a):
    """One-off real test: separate edition id, '【测试】' subject, allowed while EMAIL_SEND_ENABLED=false."""
    if not a.confirm_real_email:
        raise SystemExit("this sends REAL email to the configured recipients; add --confirm-real-email")
    import time as _t
    o = _load(a.article); render.finalize(o)
    o = dict(o, edition_id=f"{o['edition_id']}-test-{_t.strftime('%Y%m%d%H%M%S')}", title=dict(o["title"], zh="【测试】" + o["title"]["zh"]))
    render.finalize(o); out = data_dir() / "outbox-test"; render.build([dict(o)], out, a.base_url)
    html = (out / "email" / f"{o['edition_id']}.html").read_text(encoding="utf-8"); text = (out / "email" / f"{o['edition_id']}.txt").read_text(encoding="utf-8")
    d = db()
    try:
        rep = mailer.send_edition(d, o, html, text, config.load_runtime(), mode="real", manual_test=True)
    except (mailer.SendDisabled, mailer.ConfigIncomplete) as e:
        print(json.dumps({"sent": False, "reason": str(e)}, ensure_ascii=False)); return 2
    done = state.delivery_complete(d, o["edition_id"], o["revision"])
    print(json.dumps({"test_edition": o["edition_id"], "all_accepted": done, "deliveries": rep,
                      "next": "check both inboxes and spam folders; reply once to confirm the Reply-To path"}, ensure_ascii=False, indent=1))
    return 0 if done else 3


def cmd_prepare_queue(a):
    import time
    d = db(); t0 = time.monotonic(); done = []
    with publish.lock("prepare"):
        for p in sorted((REPO / "config/candidates").glob("*.json")):
            c = pipeline.load_candidate(p)
            if state.get(d, c["candidate_id"]):
                continue
            if len(done) >= a.max_articles or (time.monotonic() - t0) / 60 > a.budget_minutes:
                break
            try:
                rep = pipeline.prepare(c, d)
            except Exception as e:             # one bad candidate must not stop the queue
                rep = {"outcome": "error", "reason": f"{type(e).__name__}: {e}"[:300], "wall_s": round(time.monotonic() - t0, 1)}
            done.append({"candidate": c["candidate_id"], "outcome": rep.get("outcome"), "reason": rep.get("reason", "")[:200], "wall_s": rep.get("wall_s")})
    print(json.dumps({"processed": done, "inventory": pipeline.inventory(d)}, ensure_ascii=False, indent=1)); return 0


def cmd_publish_today(a):
    with publish.lock("publish"):
        rep = publish.publish_today(db(), config.load_runtime(), date=a.date)
    print(json.dumps(rep, ensure_ascii=False, indent=1)); return publish.EXIT.get(rep.get("outcome"), 4)


def cmd_supply(a):
    d = db()
    if a.check:
        print(json.dumps(supply.check_catalogue(), ensure_ascii=False, indent=1)); return 0
    inv = pipeline.inventory(d); rot = config.load_project()["rotation"]
    cats = [a.category] if a.category else sorted(rot, key=lambda c: (-inv["gaps_to_target"].get(c, 0), inv["schedulable_by_category"].get(c, 0)))
    out = []
    with publish.lock("prepare"):
        for c in cats[: a.max]:
            e = supply.pick_entry(c)
            out.append(supply.propose(e, d) if e else {"category": c, "outcome": "rejected", "reason": "no catalogue entry for category"})
    print(json.dumps([{k: v for k, v in r.items() if k != "raw"} for r in out], ensure_ascii=False, indent=1))
    return 0 if any(r.get("outcome") == "candidate" for r in out) else 2


EDITABLE = ("checker BLOCK", "awaiting editor stage", "review missing", "editor:", "requeued for editor")


def _evidence_for(article_path: Path) -> Path:
    p = article_path.parent / "evidence.json"
    if p.exists():
        return p
    m = REPO / "samples" / f"evidence_{article_path.parent.name}.json"
    return m


def _workdir(d, cid: str, article: Path | None = None) -> Path | None:
    """Fresh editor attempt dir seeded from: an explicit article file (manual edit) > previous attempt > admitted path > model draft."""
    root = data_dir() / "editor" / cid; prev = sorted(root.glob("attempt-*"), key=lambda p: int(p.name.split("-")[1])) if root.exists() else []
    w = root / f"attempt-{len(prev) + 1}"; w.mkdir(parents=True, exist_ok=True)
    draft = data_dir() / "drafts" / cid; cur = state.get(d, cid)
    if article:
        src_art = Path(article); src_ev, src_rv = _evidence_for(src_art), None
    elif prev and (prev[-1] / "edited.json").exists():
        src_art, src_ev, src_rv = prev[-1] / "edited.json", prev[-1] / "evidence.json", None
        rec = prev[-1] / "editor_record.json"
        if rec.exists():                               # carry the open issues into this attempt
            (w / "seed_issues.json").write_text(json.dumps(_load(rec).get("remaining", []), ensure_ascii=False, indent=1), encoding="utf-8")
    elif cur and cur.get("path") and Path(cur["path"]).exists() and Path(cur["path"]).parent != draft:
        src_art = Path(cur["path"]); src_ev, src_rv = _evidence_for(src_art), None
    elif (draft / "article.json").exists():
        src_art, src_ev, src_rv = draft / "article.json", draft / "evidence.json", draft / "review_zh.json"
    else:
        return None
    shutil.copy(src_art, w / "article.json"); shutil.copy(src_ev, w / "evidence.json")
    if src_rv and src_rv.exists():
        shutil.copy(src_rv, w / "review_zh.json")
    return w


def _publish_attempt(w: Path, cid: str, record: dict) -> Path:
    """Copy the edited article, evidence, record and model outputs into samples/auto/<cid>/ (git)."""
    out = REPO / "samples/auto" / cid; out.mkdir(parents=True, exist_ok=True)
    o = _load(w / "edited.json"); render.finalize(o)
    (out / "article.json").write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copy(w / "evidence.json", out / "evidence.json"); shutil.copy(w / "editor_record.json", out / "editor_record.json")
    for f in w.glob("*.json"):
        if f.name.startswith(("edit_r", "rereview_", "parity_")):
            shutil.copy(f, out / f"{w.name}_{f.name}")
    (out / "article.zh.md").write_text(render.markdown(o, "zh"), encoding="utf-8"); (out / "article.en.md").write_text(render.markdown(o, "en"), encoding="utf-8")
    return out


def _edit_one(d, cid: str, max_rounds=editor.MAX_ROUNDS, article: Path | None = None) -> dict:
    cur = state.get(d, cid)
    if not cur or cur["status"] != "pending_review":
        return {"edition": cid, "outcome": "skipped", "reason": f"status {cur['status'] if cur else 'unknown'}"}
    w = _workdir(d, cid, article)
    if not w:
        return {"edition": cid, "outcome": "skipped", "reason": "no draft to edit"}
    rec = editor.edit(w, max_rounds=max_rounds)
    out = _publish_attempt(w, cid, rec)
    res = {"edition": cid, "attempt": w.name, "edits": rec["edits_total"], "model_calls": rec["model_calls"],
           "model_wall_s": rec["model_wall_s"], "remaining": len(rec["remaining"])}
    if rec["outcome"] == "admissible":
        res.update(editor.admit_with_record(d, out / "article.json", out / "evidence.json", rec))
        res["outcome"] = "admitted" if res.get("admitted") else "pending_review"
    else:
        why = f"editor: {len(rec['remaining'])} issues remain after {len([r for r in rec['rounds'] if r['round']])} round(s) ({w.name})"
        state.transition(d, cid, "prepared", note=why); state.transition(d, cid, "pending_review", note=why, reason=why)
        res.update(outcome="pending_review", reason=why)
    return res


def cmd_edit(a):
    d = db()
    with publish.lock("prepare"):
        r = _edit_one(d, a.edition, max_rounds=a.rounds or editor.MAX_ROUNDS)
    print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r.get("outcome") == "admitted" else 2


def _edit_queue(d, max_n, budget_min, max_attempts=None):
    max_attempts = max_attempts or int(config.load_project().get("editor", {}).get("max_attempts", 2))
    import time as _t
    t0 = _t.monotonic(); out = []
    rows = d.execute("SELECT edition_id, COALESCE(reason,'') FROM edition WHERE status='pending_review' ORDER BY updated_at").fetchall()
    for cid, why in rows:
        if len(out) >= max_n or (_t.monotonic() - t0) / 60 > budget_min:
            break
        tries = len(list((data_dir() / "editor" / cid).glob("attempt-*"))) if (data_dir() / "editor" / cid).exists() else 0
        if not why.startswith(EDITABLE) or tries >= max_attempts:
            continue                     # refusals, failed model steps, duplicates and exhausted drafts wait for a person
        try:
            out.append(_edit_one(d, cid))
        except Exception as e:
            out.append({"edition": cid, "outcome": "error", "reason": f"{type(e).__name__}: {e}"[:300]})
    return out


def cmd_edit_queue(a):
    d = db()
    with publish.lock("prepare"):
        out = _edit_queue(d, a.max, a.budget_minutes)
    print(json.dumps({"edited": out, "inventory": pipeline.inventory(d)}, ensure_ascii=False, indent=1)); return 0


def _final_one(d, cid: str) -> dict:
    from . import final_edit
    cur = state.get(d, cid)
    if not cur or cur["status"] != "pending_review":
        return {"edition": cid, "outcome": "skipped", "reason": f"status {cur['status'] if cur else 'unknown'}"}
    rec = final_edit.run(cid, d)
    res = {"edition": cid, "outcome": rec["outcome"], "elapsed_min": rec.get("elapsed_min"), "open_issues": rec.get("open_issues"),
           "failure": rec.get("failure") or rec.get("reason"), "edits": len(rec.get("edits", [])), "issues": len(rec.get("issues", []))}
    if rec["outcome"] == "admissible":
        out = final_edit.OUT_ROOT / cid / "final"
        res.update(final_edit.admit(d, out / "article.json", out / "evidence.json", rec))
        res["outcome"] = "admitted" if res.get("admitted") else "pending_review"
    elif rec["outcome"] == "pending_review":
        why = f"final editor: {len(rec.get('open_issues') or [])} open issue(s)" + (f"; {rec['failure']}" if rec.get("failure") else "")
        state.transition(d, cid, "prepared", note=why); state.transition(d, cid, "pending_review", note=why, reason=why)
    return res


def cmd_final_edit(a):
    """Named final editor (Pi-local Claude Code CLI) on pending editions; admits only through a verified record."""
    d = db(); out = []
    with publish.lock("prepare"):
        for cid in a.editions:
            try:
                out.append(_final_one(d, cid))
            except Exception as e:
                out.append({"edition": cid, "outcome": "error", "reason": f"{type(e).__name__}: {e}"[:300]})
    print(json.dumps({"final_edit": out, "inventory": pipeline.inventory(d)}, ensure_ascii=False, indent=1))
    return 0 if all(r.get("outcome") == "admitted" for r in out) else 2


def cmd_rereview(a):
    """Admitted edition without a bound review (e.g. a manual editor pass): requeue, then run the editor stage
    with zero edit rounds; it is re-admitted only if the fresh review and parity check of its current content are clean."""
    d = db(); cur = state.get(d, a.edition)
    if not cur or cur["status"] not in ("checked", "pending_review"):
        print(json.dumps({"edition": a.edition, "error": f"status {cur['status'] if cur else 'unknown'}"})); return 1
    with publish.lock("prepare"):
        if cur["status"] == "checked":
            state.transition(d, a.edition, "pending_review", note="requeued for editor re-review", reason="requeued for editor re-review")
            if cur.get("episode_id"): registry.set_status(d, cur["episode_id"], "prepared")
        r = _edit_one(d, a.edition, max_rounds=a.rounds, article=Path(a.article) if a.article else None)
    print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r.get("outcome") == "admitted" else 2


def cmd_nightly(a):
    """One batch: top up candidates (if fewer than --min-candidates), prepare, then edit. Budgeted; never schedules or sends."""
    import time as _t
    d = db(); t0 = _t.monotonic(); rep = {}
    with publish.lock("prepare"):
        inv = pipeline.inventory(d)
        if inv["candidates_unprocessed"] < a.min_candidates:
            rot = config.load_project()["rotation"]
            cats = sorted(rot, key=lambda c: (-inv["gaps_to_target"].get(c, 0), inv["schedulable_by_category"].get(c, 0)))
            rep["supply"] = [{k: v for k, v in supply.propose(supply.pick_entry(c), d).items() if k not in ("raw", "dropped")}
                             for c in cats[: a.min_candidates - inv["candidates_unprocessed"]] if supply.pick_entry(c)]
        rep["prepare"] = []
        for p in sorted((REPO / "config/candidates").glob("*.json")):
            c = pipeline.load_candidate(p)
            if state.get(d, c["candidate_id"]) or len(rep["prepare"]) >= a.max_articles or (_t.monotonic() - t0) / 60 > a.budget_minutes:
                continue
            try:
                r = pipeline.prepare(c, d)
            except Exception as e:
                r = {"outcome": "error", "reason": f"{type(e).__name__}: {e}"[:300]}
            rep["prepare"].append({"candidate": c["candidate_id"], "outcome": r.get("outcome"), "reason": str(r.get("reason", ""))[:200]})
        rep["edit"] = _edit_queue(d, a.max_articles, max(0, a.budget_minutes - (_t.monotonic() - t0) / 60))
    rep["inventory"] = pipeline.inventory(d)
    print(json.dumps(rep, ensure_ascii=False, indent=1)); return 1 if rep["inventory"]["alert"] else 0


def cmd_admit(a):
    """Admit an article into inventory. Pending drafts need an editor record bound to this exact content and evidence;
    remaining FIX-level issues need a named --exception. --as-sample registers a sample that is never schedulable
    until `hip approve-sample`."""
    o = _load(a.article); ev = _load(a.evidence); render.finalize(o); d = db()
    f, st = checks.check(o, ev)
    if checks.blocked(f):
        print(json.dumps({"admitted": False, "reason": "checker BLOCK", "findings": f}, ensure_ascii=False, indent=1)); return 1
    if not o.get("episode"):
        print(json.dumps({"admitted": False, "reason": "article has no episode metadata"}, ensure_ascii=False)); return 1
    cur = state.get(d, o["edition_id"])
    if cur and cur["status"] == "pending_review":
        if not a.record:
            print(json.dumps({"admitted": False, "reason": "pending draft: --record EDITOR_RECORD.json required (run `hip edit`)"}, ensure_ascii=False)); return 1
        exc = dict(x.split("=", 1) for x in a.exception if "=" in x) if a.exception else None
        if a.exception and any("=" not in x for x in a.exception):
            exc = " ".join(a.exception)                # refused downstream: a whole-article exception
        r = editor.admit_with_record(d, Path(a.article), Path(a.evidence), _load(a.record), exception=exc)
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r.get("admitted") else 1
    if cur:
        print(json.dumps({"admitted": False, "reason": f"already known: {cur['status']}"}, ensure_ascii=False)); return 0
    if not a.as_sample:
        print(json.dumps({"admitted": False, "reason": "new articles enter through the pipeline (prepare -> edit) or as samples (--as-sample)"},
                         ensure_ascii=False)); return 1
    eid, v = registry.reserve(d, dict(o["episode"], episode_id=o.get("episode_id"), title=o["title"]["zh"], category=o["category"]), status="checked")
    if not eid:
        print(json.dumps({"admitted": False, "reason": f"{v[0]}: {v[1]}"}, ensure_ascii=False)); return 1
    state.transition(d, o["edition_id"], "prepared", note="sample registered", episode_id=eid, category=o["category"], path=str(Path(a.article).resolve()))
    state.transition(d, o["edition_id"], "checked", note="sample: not schedulable until approve-sample", content_sha256=o["content_sha256"], origin="sample")
    print(json.dumps({"admitted": True, "edition_id": o["edition_id"], "episode_id": eid, "origin": "sample", "schedulable": False, "stats": st},
                     ensure_ascii=False)); return 0


def cmd_approve_sample(a):
    d = db(); cur = state.get(d, a.edition)
    if not cur or cur["status"] != "checked" or (cur.get("origin") or "") != "sample":
        print(json.dumps({"approved": False, "reason": "not a checked sample"})); return 1
    d.execute("UPDATE edition SET approval=? WHERE edition_id=?", (f"sample-approved: {a.reason}", a.edition))
    d.execute("INSERT INTO transition(edition_id,from_status,to_status,at,note) VALUES(?,?,?,?,?)",
              (a.edition, "checked", "checked", __import__("time").time(), f"sample approved: {a.reason}"))
    print(json.dumps({"approved": True, "edition": a.edition}, ensure_ascii=False)); return 0


def cmd_requeue(a):
    """Send a `checked` (not yet scheduled) edition back to the pending queue, with a reason."""
    d = db(); cur = state.get(d, a.edition)
    if not cur or cur["status"] != "checked":
        print(json.dumps({"requeued": False, "reason": f"status is {cur['status'] if cur else 'unknown'}"})); return 1
    state.transition(d, a.edition, "pending_review", note=a.reason, reason=a.reason)
    if cur.get("episode_id"): registry.set_status(d, cur["episode_id"], "prepared")
    print(json.dumps({"requeued": True, "edition": a.edition}, ensure_ascii=False)); return 0


def cmd_status(a):
    d = db(); s = state.summary(d)
    s["recent"] = [dict(zip(("edition_id", "status", "category", "reason"), r)) for r in
                   d.execute("SELECT edition_id,status,category,substr(COALESCE(reason,''),1,160) FROM edition ORDER BY updated_at DESC LIMIT 15")]
    s["deliveries"] = [dict(zip(("edition", "rev", "recipient", "status", "attempts", "error"), r)) for r in
                       d.execute("SELECT edition_id,revision,recipient_label,status,attempts,last_error FROM delivery ORDER BY updated_at DESC LIMIT 20")]
    print(json.dumps(s, ensure_ascii=False, indent=1)); return 0


def cmd_inventory(a):
    if a.what_if:                      # arithmetic only: counts you name, not editions that exist or are approved
        rot = config.load_project()["rotation"]; ab = {c[0].upper() if c != "china_modern" else "M": c for c in rot}
        ab.update({"A": "china_ancient", "W": "world", "M": "china_modern", "U": "us"})
        counts = {c: 0 for c in rot}
        for part in a.what_if.split(","):
            k, n = part.split("="); counts[ab.get(k.strip(), k.strip())] += int(n)
        start = a.start or rot[0]; seq = pipeline.rotation_days(counts, rot, start)
        print(json.dumps({"what_if": counts, "start": start, "coverage_days": len(seq), "sequence": seq,
                          "stops_at": rot[(rot.index(start) + len(seq)) % len(rot)],
                          "basis": "hypothetical counts; same rotation_days() as `hip inventory`"}, ensure_ascii=False, indent=1)); return 0
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
    p = sp.add_parser("prepare-queue"); p.add_argument("--max-articles", type=int, default=3); p.add_argument("--budget-minutes", type=float, default=150)
    p.set_defaults(f=cmd_prepare_queue)
    p = sp.add_parser("publish-today"); p.add_argument("--date"); p.set_defaults(f=cmd_publish_today)
    p = sp.add_parser("send-test"); p.add_argument("article"); p.add_argument("--confirm-real-email", action="store_true")
    p.add_argument("--base-url", default="https://starhub.vip"); p.set_defaults(f=cmd_send_test)
    p = sp.add_parser("supply"); p.add_argument("--category"); p.add_argument("--max", type=int, default=1); p.add_argument("--check", action="store_true")
    p.set_defaults(f=cmd_supply)
    p = sp.add_parser("edit"); p.add_argument("edition"); p.add_argument("--rounds", type=int, help="override editor.max_rounds for this attempt")
    p.set_defaults(f=cmd_edit)
    p = sp.add_parser("edit-queue"); p.add_argument("--max", type=int, default=3); p.add_argument("--budget-minutes", type=float, default=120)
    p.set_defaults(f=cmd_edit_queue)
    p = sp.add_parser("rereview"); p.add_argument("edition"); p.add_argument("--rounds", type=int, default=0)
    p.add_argument("--article", help="re-review this file (e.g. after a manual editor pass) instead of the stored version"); p.set_defaults(f=cmd_rereview)
    p = sp.add_parser("final-edit"); p.add_argument("editions", nargs="+"); p.set_defaults(f=cmd_final_edit)
    p = sp.add_parser("nightly"); p.add_argument("--max-articles", type=int, default=2); p.add_argument("--budget-minutes", type=float, default=150)
    p.add_argument("--min-candidates", type=int, default=2); p.set_defaults(f=cmd_nightly)
    p = sp.add_parser("approve-sample"); p.add_argument("edition"); p.add_argument("--reason", required=True); p.set_defaults(f=cmd_approve_sample)
    for name, f in (("status", cmd_status), ("recover", cmd_recover)):
        sp.add_parser(name).set_defaults(f=f)
    p = sp.add_parser("inventory"); p.add_argument("--what-if", help="hypothetical counts, e.g. A=1,W=2,M=2,U=1"); p.add_argument("--start")
    p.set_defaults(f=cmd_inventory)
    p = sp.add_parser("requeue"); p.add_argument("edition"); p.add_argument("--reason", required=True); p.set_defaults(f=cmd_requeue)
    p = sp.add_parser("admit"); p.add_argument("article"); p.add_argument("evidence"); p.add_argument("--record")
    p.add_argument("--exception", action="append", metavar="ISSUE_ID=REASON", help="per-issue owner exception; repeat once per open issue")
    p.add_argument("--as-sample", action="store_true"); p.add_argument("--from-pending", action="store_true", help="kept for compatibility; implied")
    p.set_defaults(f=cmd_admit)
    p = sp.add_parser("registry-rebuild"); p.add_argument("content", nargs="+"); p.add_argument("--db"); p.set_defaults(f=cmd_registry_rebuild)
    a = ap.parse_args(argv)
    state.recover(db()) if a.cmd not in ("doctor",) else None
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())

"""Dedup validation (P1-3). Run with a python that has `opencc` (t2s).
Demonstrates: immutable episode registry; parent_event vs episode; alias /
繁简 / Latin-name normalisation; QID redirects; source-span overlap as the
strongest duplicate signal; reservation of prepared/scheduled items with a
DB uniqueness constraint; CJK 2-char recall; rebuild from exported JSON.
Prints a PASS/FAIL table. Test data is synthetic; QIDs are fake (Q-TEST-*)."""
import json, re, sqlite3, sys, tempfile
from pathlib import Path
from opencc import OpenCC
t2s = OpenCC("t2s").convert
ACTIVE = ("reserved", "prepared", "scheduled", "published")

SCHEMA = """
CREATE TABLE episode(
  episode_id TEXT PRIMARY KEY, status TEXT NOT NULL, title TEXT, category TEXT,
  parent_event TEXT, event_qid TEXT, persons TEXT, year_from INT, year_to INT,
  place TEXT, action TEXT, primary_anchor TEXT NOT NULL, spans TEXT NOT NULL, search_text TEXT);
CREATE UNIQUE INDEX one_active_per_anchor ON episode(primary_anchor)
  WHERE status IN ('reserved','prepared','scheduled','published');
CREATE TABLE alias(alias TEXT PRIMARY KEY, entity TEXT NOT NULL);
CREATE TABLE qid_redirect(old TEXT PRIMARY KEY, new TEXT NOT NULL);
CREATE TABLE seq(n INTEGER);
CREATE VIRTUAL TABLE fts_unicode USING fts5(body);
CREATE VIRTUAL TABLE fts_trigram USING fts5(body, tokenize='trigram');
CREATE VIRTUAL TABLE fts_bigram  USING fts5(body);   -- body = space-joined CJK bigrams
"""
ALIASES = {"陈平":"Q-TEST-CHENPING","陳平":"Q-TEST-CHENPING","chen ping":"Q-TEST-CHENPING","曲逆侯":"Q-TEST-CHENPING",
           "范增":"Q-TEST-FANZENG","亚父":"Q-TEST-FANZENG","fan zeng":"Q-TEST-FANZENG",
           "项羽":"Q-TEST-XIANGYU","項羽":"Q-TEST-XIANGYU","项王":"Q-TEST-XIANGYU","xiang yu":"Q-TEST-XIANGYU",
           "刘邦":"Q-TEST-LIUBANG","汉王":"Q-TEST-LIUBANG","纪信":"Q-TEST-JIXIN",
           "shackleton":"Q-TEST-SHACKLETON","worsley":"Q-TEST-WORSLEY","wild":"Q-TEST-WILD"}
WORKS = {"史記":"shiji","史记":"shiji","shiji":"shiji","records of the grand historian":"shiji","south":"shackleton-south"}

def norm_name(s): return t2s(s.strip()).lower()
def entity(db, s):
    n = norm_name(s); r = db.execute("SELECT entity FROM alias WHERE alias=?", (n,)).fetchone()
    return r[0] if r else "name:" + n
def canon_qid(db, q):
    seen = set()
    while q and q not in seen:
        seen.add(q); r = db.execute("SELECT new FROM qid_redirect WHERE old=?", (q,)).fetchone()
        if not r: break
        q = r[0]
    return q
def spans(c):  # [(work, chapter, para_from, para_to)] canonical passage keys;
    # translations/editions must map to the ORIGINAL work's chapter+paragraph numbering
    return [(WORKS.get(norm_name(w), norm_name(w)), str(ch), a, b) for w, ch, a, b in c["sources"]]
def bigrams(s):
    s = t2s(s); cjk = re.findall(r"[一-鿿]+", s); out = []
    for run in cjk: out += [run[i:i+2] for i in range(len(run)-1)] or [run]
    return " ".join(out + re.findall(r"[a-z0-9]+", s.lower()))

def overlap(x, y):
    return any(a[0]==b[0] and a[1]==b[1] and a[2] < b[3] and b[2] < a[3] for a in x for b in y)
def action_sim(a, b):
    A, B = set(bigrams(a).split()), set(bigrams(b).split())
    return len(A & B) / max(1, len(A | B))

def check(db, c):
    """-> ('duplicate'|'review'|'distinct', reason). Compares with ALL active
    episodes (reserved/prepared/scheduled/published), not only published."""
    ps = {entity(db, p) for p in c["persons"]}; sp = spans(c); q = canon_qid(db, c.get("event_qid"))
    worst = ("distinct", "")
    for row in db.execute(f"SELECT * FROM episode WHERE status IN {ACTIVE}"):
        r = dict(zip([d[0] for d in db.execute('SELECT * FROM episode LIMIT 0').description], row))
        rps = set(json.loads(r["persons"])); rsp = [tuple(x) for x in json.loads(r["spans"])]
        if q and r["event_qid"] and q == canon_qid(db, r["event_qid"]):
            return ("duplicate", f"same event QID as {r['episode_id']}")
        if overlap(sp, rsp) and ps & rps:
            return ("duplicate", f"same source passage + person as {r['episode_id']}")
        same_core = ps & rps and r["place"] == t2s(c["place"]) and not (c["year_to"] < r["year_from"] or r["year_to"] < c["year_from"])
        if same_core and action_sim(c["action"], r["action"]) >= 0.35:
            worst = ("review", f"same people/place/time and similar action as {r['episode_id']}")
        elif same_core and worst[0] == "distinct":
            worst = ("distinct", f"same people/place/time as {r['episode_id']} but different source passage and action")
    return worst

def register(db, c, status):
    """Atomic check-and-reserve. Assigns an immutable sequential ID; the ID
    itself carries no dedup meaning."""
    db.execute("BEGIN IMMEDIATE")
    try:
        verdict = check(db, c)
        if verdict[0] == "duplicate":
            db.execute("ROLLBACK"); return None, verdict
        n = db.execute("SELECT COALESCE(MAX(n),0)+1 FROM seq").fetchone()[0]; db.execute("INSERT INTO seq VALUES(?)", (n,))
        eid = f"ep-{n:06d}"; sp = spans(c)
        anchor = "|".join(map(str, sp[0][:2])) + f"@{sp[0][2]}"   # core passage = first canonical paragraph
        db.execute("INSERT INTO episode VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            eid, status, c["title"], c["category"], c.get("parent_event"), canon_qid(db, c.get("event_qid")),
            json.dumps(sorted({entity(db, p) for p in c["persons"]})), c["year_from"], c["year_to"],
            t2s(c["place"]), t2s(c["action"]), anchor, json.dumps(sp), t2s(c["title"] + " " + c["summary"])))
        body = t2s(c["title"] + " " + c["summary"])
        db.execute("INSERT INTO fts_unicode VALUES(?)", (body,)); db.execute("INSERT INTO fts_trigram VALUES(?)", (body,))
        db.execute("INSERT INTO fts_bigram VALUES(?)", (bigrams(body),))
        db.execute("COMMIT"); return eid, verdict
    except sqlite3.IntegrityError as e:
        db.execute("ROLLBACK"); return None, ("duplicate", f"reservation constraint: {e}")

def new_db(path=":memory:"):
    db = sqlite3.connect(path, isolation_level=None); db.executescript(SCHEMA)
    db.executemany("INSERT OR IGNORE INTO alias VALUES(?,?)", [(norm_name(a), e) for a, e in ALIASES.items()])
    db.execute("INSERT INTO qid_redirect VALUES('Q-TEST-OLD-NEWBURGH','Q-TEST-NEWBURGH')")
    return db

BASE = [
 dict(title="陈平反间，范增离开项羽", summary="汉王出黄金四万斤，陈平行反间，项羽疑范增，范增求去。", category="china_ancient",
      persons=["陈平","范增","项羽","汉王"], year_from=-204, year_to=-204, place="荥阳", action="反间离间项羽与范增",
      sources=[("史記","56",14,17),("史記","7",41,42)]),
 dict(title="Shackleton orders the Endurance abandoned", summary="Endurance crushed by ice; the crew camps on the floe.", category="world",
      persons=["Shackleton","Wild"], year_from=1915, year_to=1915, place="weddell sea", action="abandon ship and camp on ice",
      parent_event="Q-TEST-ITAE", sources=[("South","4",3,9)]),
 dict(title="Washington at Newburgh", summary="Officers' meeting, 15 March 1783.", category="us",
      persons=["Washington"], year_from=1783, year_to=1783, place="newburgh", action="address to officers",
      event_qid="Q-TEST-NEWBURGH", sources=[("JCC","1783-03-15",1,6)]),
]
CASES = [
 ("retitled same episode", dict(BASE[0], title="一起做事的人为什么会离开：范增之去"), "duplicate"),
 ("English edition", dict(BASE[0], title="Why Fan Zeng left Xiang Yu", summary="Chen Ping's gold sowed distrust.", persons=["Chen Ping","Fan Zeng","Xiang Yu"],
     sources=[("Records of the Grand Historian","56",15,16)]), "duplicate"),
 ("traditional characters", dict(BASE[0], title="陳平反間", persons=["陳平","范增","項羽"], place="滎陽"), "duplicate"),
 ("alias only (亚父/项王/汉王), other category", dict(BASE[0], title="亚父之死", persons=["亚父","项王"], category="world"), "duplicate"),
 ("QID missing, same passage", dict(BASE[0], title="四万斤金", persons=["陈平"], sources=[("史记","56",15,16)]), "duplicate"),
 ("QID redirect", dict(BASE[2], title="The spectacles moment", event_qid="Q-TEST-OLD-NEWBURGH", sources=[("Shaw","memoir",101,104)]), "duplicate"),
 ("same parent expedition, different episode", dict(BASE[1], title="The James Caird voyage", persons=["Shackleton","Worsley"], year_from=1916, year_to=1916,
     place="southern ocean", action="small-boat voyage to South Georgia", sources=[("South","9",1,12)]), "distinct"),
 ("same episode retold from a different work, paraphrased", dict(BASE[0], title="黄金与猜疑", summary="资治通鉴所记离间事。",
     persons=["陈平","范增"], action="陈平用金离间项羽与范增", sources=[("資治通鑑","10",30,31)]), "review"),
 ("same person/year/place, different decision", dict(BASE[0], title="纪信诳楚，汉王出荥阳", summary="纪信假扮汉王出降。", persons=["刘邦","纪信"],
     action="纪信假扮汉王出降，汉王从西门出逃", sources=[("史記","7",42,43)]), "distinct"),
]

def main():
    rows = []; db = new_db()
    for b in BASE: register(db, b, "published")
    for name, c, want in CASES:
        got = check(db, c); rows.append((name, want, got[0], got[1]))
    # reservation: a prepared (unpublished) item blocks a later duplicate, and the
    # unique index blocks a racing insert even if the app check were skipped
    eid, _ = register(db, dict(BASE[0], title="待排期：陈平离楚", persons=["陈平"], action="陈平离开项羽投汉",
                     sources=[("史記","56",5,8)]), "prepared")
    got = check(db, dict(BASE[0], title="Chen Ping defects", persons=["Chen Ping"], sources=[("shiji","56",6,7)]))
    rows.append(("duplicate of a prepared (unpublished) item", "duplicate", got[0], got[1]))
    try:
        db.execute("INSERT INTO episode VALUES('ep-race','prepared','x','x',NULL,NULL,'[]',0,0,'','',(SELECT primary_anchor FROM episode WHERE episode_id=?),'[]','')", (eid,))
        rows.append(("racing insert on same core passage", "rejected", "accepted", "unique index missing"))
    except sqlite3.IntegrityError as e:
        rows.append(("racing insert on same core passage", "rejected", "rejected", str(e)))
    # rebuild from exported published JSON (simulates SQLite loss)
    with tempfile.TemporaryDirectory() as d:
        for i, b in enumerate(BASE): Path(d, f"{i}.json").write_text(json.dumps(b, ensure_ascii=False))
        db2 = new_db()
        for f in sorted(Path(d).glob("*.json")): register(db2, json.loads(f.read_text()), "published")
        same = all(check(db2, c)[0] == check(db, c)[0] for _, c, _ in CASES)
        rows.append(("rebuild from exported JSON gives same verdicts", "same", "same" if same else "differs", ""))
    # CJK recall for a 2-character name
    q = "陈平"
    u = db.execute("SELECT count(*) FROM fts_unicode WHERE fts_unicode MATCH ?", (q,)).fetchone()[0]
    try: tg = db.execute("SELECT count(*) FROM fts_trigram WHERE fts_trigram MATCH ?", (q,)).fetchone()[0]
    except sqlite3.OperationalError: tg = "error"
    bg = db.execute("SELECT count(*) FROM fts_bigram WHERE fts_bigram MATCH ?", (f'"{q}"',)).fetchone()[0]
    ins = db.execute("SELECT count(*) FROM episode WHERE instr(search_text, ?) > 0", (q,)).fetchone()[0]
    rows.append((f"recall '{q}': unicode61={u} trigram={tg} bigram={bg} instr={ins}", "bigram>0 and instr>0",
                 "ok" if bg and ins else "miss", f"sqlite {sqlite3.sqlite_version}"))
    ok = True
    for name, want, got, why in rows:
        p = (want == got) or (want == "bigram>0 and instr>0" and got == "ok")
        ok &= p; print(f"{'PASS' if p else 'FAIL'} | {name} | want={want} got={got} | {why}")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()

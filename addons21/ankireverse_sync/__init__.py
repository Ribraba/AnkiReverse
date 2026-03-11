"""
AnkiReverse Sync — Add-on Anki 2.1.26
- Lit les cartes via mw.col.db (dans le processus Anki, pas de verrou SQLite)
- Parle à Turso via HTTP API + urllib (aucune dépendance externe)
"""
import json
import time
import threading
import urllib.request
from pathlib import Path

from aqt import mw, gui_hooks
from aqt.utils import showInfo
from aqt.qt import QAction

ENV_FILE = Path.home() / "Documents/Projets/CODE/AnkiReverse/.env"


# ── Config ────────────────────────────────────────────────────────────────────

def load_env() -> dict:
    env = {}
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def turso_url(env: dict) -> str:
    """Convertit libsql:// en https:// pour l'API HTTP."""
    url = env.get("TURSO_URL", "")
    return url.replace("libsql://", "https://")


# ── Turso HTTP API ─────────────────────────────────────────────────────────────

def turso_query(base_url: str, token: str, statements: list) -> list:
    """
    Envoie plusieurs requêtes SQL à Turso via /v2/pipeline.
    statements = [{"sql": "...", "args": [{"type":"text","value":"..."}]}, ...]
    Retourne la liste des results.
    """
    requests_payload = [{"type": "execute", "stmt": s} for s in statements]
    requests_payload.append({"type": "close"})

    body = json.dumps({"requests": requests_payload}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/v2/pipeline",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    results = []
    for r in data.get("results", []):
        if r.get("type") == "ok":
            results.append(r["response"].get("result", {}))
    return results


def to_turso_arg(value):
    """Convertit une valeur Python en argument Turso typé."""
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": str(value)}
    return {"type": "text", "value": str(value)}


# ── Lecture Anki (mw.col.db) ──────────────────────────────────────────────────

def collect_cards() -> list:
    """Lit toutes les cartes via mw.col.db.all() — aucun verrou SQLite."""
    rows = mw.col.db.all("""
        SELECT c.id, c.nid, c.did, c.ord, c.queue, c.type,
               c.due, c.ivl, c.factor, c.reps, c.lapses, c.mod,
               n.flds, n.tags, n.mid
        FROM cards c JOIN notes n ON c.nid = n.id
    """)

    models = json.loads(mw.col.db.scalar("SELECT models FROM col") or "{}")
    decks  = json.loads(mw.col.db.scalar("SELECT decks FROM col")  or "{}")

    batch = []
    for row in rows:
        cid, nid, did, ord_, queue, ctype, due, ivl, factor, reps, lapses, mod, flds, tags, mid = row
        fields  = flds.split("\x1f")
        model   = models.get(str(mid), {})
        deck    = decks.get(str(did), {})
        mfields = model.get("flds", [])
        tmpls   = model.get("tmpls", [{}])
        tmpl    = tmpls[ord_] if ord_ < len(tmpls) else tmpls[0]
        fmap    = {f["name"]: fields[i] for i, f in enumerate(mfields) if i < len(fields)}
        batch.append({
            "id": cid, "nid": nid,
            "deck": deck.get("name", "Default"),
            "model": model.get("name", "Basic"),
            "fields": json.dumps(fmap, ensure_ascii=False),
            "q": tmpl.get("qfmt", ""),
            "a": tmpl.get("afmt", ""),
            "css": model.get("css", ""),
            "tags": tags.strip(),
            "queue": queue, "type": ctype, "due": due,
            "ivl": ivl, "factor": factor, "reps": reps, "lapses": lapses, "mod": mod,
        })
    return batch


def apply_reviews(reviews: list) -> int:
    """Applique les révisions Turso dans mw.col.db."""
    if not reviews:
        return 0

    now = int(time.time())
    crt = mw.col.db.scalar("SELECT crt FROM col WHERE id=1") or 0
    rrow = mw.col.db.first("SELECT val FROM config WHERE key='rollover'")
    rollover = int(rrow[0]) if rrow else 4
    today = (now - rollover * 3600 - (crt - rollover * 3600)) // 86400

    applied = 0
    for card_id, rating, reviewed_at in reviews:
        card = mw.col.db.first(
            "SELECT queue, type, due, ivl, factor, reps, lapses FROM cards WHERE id=?",
            card_id
        )
        if not card:
            continue
        queue, ctype, due, ivl, factor, reps, lapses = card
        new_reps   = reps + 1
        new_lapses = lapses + (1 if rating == 1 else 0)

        if rating == 1:
            new_ivl, new_factor, new_queue = 1, max(1300, factor - 200), 1
        elif rating == 2:
            new_ivl, new_factor, new_queue = max(1, int(ivl * 1.2)), max(1300, factor - 150), 2
        elif rating == 3:
            new_ivl, new_factor, new_queue = max(1, int(ivl * factor / 1000)), factor, 2
        else:
            new_ivl, new_factor, new_queue = max(1, int(ivl * factor / 1000 * 1.3)), factor + 150, 2

        new_due = today + new_ivl if new_queue == 2 else now + 600
        mw.col.db.execute(
            "UPDATE cards SET queue=?,type=2,due=?,ivl=?,factor=?,reps=?,lapses=?,mod=? WHERE id=?",
            new_queue, new_due, new_ivl, new_factor, new_reps, new_lapses, now, card_id
        )
        mw.col.db.execute(
            "INSERT OR IGNORE INTO revlog(id,cid,usn,ease,ivl,lastIvl,factor,time,type) VALUES(?,?,-1,?,?,?,?,?,1)",
            reviewed_at * 1000, card_id, rating, new_ivl, ivl, new_factor, 60000
        )
        applied += 1

    if applied:
        try:
            mw.col.save()
        except Exception:
            pass
    return applied


# ── Tâche réseau (thread arrière-plan) ────────────────────────────────────────

def turso_sync_task(cards: list, env: dict):
    """Push cards + pull reviews via Turso HTTP API."""
    base = turso_url(env)
    token = env.get("TURSO_TOKEN", "")

    # 1. Pull reviews non synchronisées
    pull_result = turso_query(base, token, [{
        "sql": "SELECT card_id, rating, reviewed_at FROM review_log WHERE synced_to_anki=0"
    }])
    reviews = []
    if pull_result:
        rows = pull_result[0].get("rows", [])
        for row in rows:
            card_id  = int(row[0]["value"])
            rating   = int(row[1]["value"])
            rev_at   = int(row[2]["value"])
            reviews.append((card_id, rating, rev_at))

    # 2. Push cards vers Turso
    stmts = []
    for c in cards:
        stmts.append({
            "sql": """INSERT OR REPLACE INTO cards
                (id,note_id,deck,model,fields,q_template,a_template,
                 css,tags,queue,type,due,interval,factor,reps,lapses,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            "args": [to_turso_arg(v) for v in (
                c["id"], c["nid"], c["deck"], c["model"], c["fields"],
                c["q"], c["a"], c["css"], c["tags"],
                c["queue"], c["type"], c["due"], c["ivl"],
                c["factor"], c["reps"], c["lapses"], c["mod"]
            )]
        })
        if len(stmts) >= 100:  # batch de 100 pour éviter les timeouts
            turso_query(base, token, stmts)
            stmts = []
    if stmts:
        turso_query(base, token, stmts)

    # 3. Marquer les reviews comme traitées
    if reviews:
        mark_stmts = [{"sql": "UPDATE review_log SET synced_to_anki=1 WHERE card_id=? AND reviewed_at=?",
                       "args": [to_turso_arg(card_id), to_turso_arg(rev_at)]}
                      for card_id, _, rev_at in reviews]
        turso_query(base, token, mark_stmts)

    return reviews, len(cards)


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_sync(show_result=True):
    if not mw.col:
        return

    env = load_env()
    if not env.get("TURSO_URL") or not env.get("TURSO_TOKEN"):
        if show_result:
            showInfo(f"AnkiReverse : fichier .env introuvable\n{ENV_FILE}", title="AnkiReverse")
        return

    # Lire les données Anki sur le thread principal
    try:
        cards = collect_cards()
    except Exception as e:
        if show_result:
            showInfo(f"AnkiReverse — Erreur lecture collection :\n{e}", title="AnkiReverse")
        return

    result_container = [None]
    error_container  = [None]

    def background():
        try:
            result_container[0] = turso_sync_task(cards, env)
        except Exception as e:
            error_container[0] = str(e)

    def check_done():
        if result_container[0] is None and error_container[0] is None:
            mw.progress.timer(500, check_done, False)
            return

        if error_container[0]:
            if show_result:
                showInfo(f"AnkiReverse — Erreur Turso :\n{error_container[0]}", title="AnkiReverse")
            return

        reviews, pushed = result_container[0]

        # Appliquer les reviews sur le thread principal
        try:
            applied = apply_reviews(reviews)
        except Exception as e:
            applied = 0

        if show_result:
            msg = f"↑ {pushed} cartes exportées"
            if applied:
                msg += f"\n↓ {applied} révisions iPhone importées"
            showInfo(msg, title="AnkiReverse ✓")

    threading.Thread(target=background, daemon=True).start()
    mw.progress.timer(500, check_done, False)


# ── Hooks ─────────────────────────────────────────────────────────────────────

_menu_added = False

def on_profile_open():
    global _menu_added
    if not _menu_added:
        action = QAction("AnkiReverse — Sync maintenant", mw)
        action.triggered.connect(lambda: run_sync(show_result=True))
        mw.form.menuTools.addAction(action)
        _menu_added = True
    # Délai 3s pour laisser Anki finir d'initialiser
    mw.progress.timer(3000, lambda: run_sync(show_result=True), False)


def on_profile_close():
    if not mw.col:
        return
    env = load_env()
    if not env.get("TURSO_URL"):
        return
    try:
        cards = collect_cards()
        turso_sync_task(cards, env)
    except Exception:
        pass


gui_hooks.profile_did_open.append(on_profile_open)
gui_hooks.profile_will_close.append(on_profile_close)

"""
AnkiReverse Sync — Add-on Anki
Synchronise automatiquement les cartes avec Turso (cloud) à l'ouverture et à la fermeture d'Anki.
"""
import threading
import sqlite3
import json
import time
from pathlib import Path

from aqt import mw
from aqt.utils import showInfo, tooltip
from aqt import gui_hooks

# ── Config ────────────────────────────────────────────────────────────────────

# Chemin vers le .env du projet AnkiReverse
ENV_FILE = Path.home() / "Documents/Projets/CODE/AnkiReverse/.env"


def load_env() -> dict:
    env = {}
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


# ── Sync logic ────────────────────────────────────────────────────────────────

def get_today_offset(anki: sqlite3.Connection) -> int:
    crt = anki.execute("SELECT crt FROM col WHERE id=1").fetchone()[0]
    row = anki.execute("SELECT val FROM config WHERE key='rollover'").fetchone()
    rollover = int(row[0]) if row else 4
    now = int(time.time())
    return (now - rollover * 3600 - (crt - rollover * 3600)) // 86400


def push_cards(anki: sqlite3.Connection, turso) -> int:
    rows = anki.execute("""
        SELECT c.id, c.nid, c.did, c.ord, c.queue, c.type,
               c.due, c.ivl, c.factor, c.reps, c.lapses, c.mod,
               n.flds, n.tags, n.mid
        FROM cards c
        JOIN notes n ON c.nid = n.id
    """).fetchall()

    models_raw = anki.execute("SELECT models FROM col").fetchone()
    decks_raw  = anki.execute("SELECT decks FROM col").fetchone()
    models = json.loads(models_raw[0]) if models_raw and models_raw[0] else {}
    decks  = json.loads(decks_raw[0])  if decks_raw and decks_raw[0]  else {}

    batch = []
    for row in rows:
        (cid, nid, did, ord_, queue, ctype, due, ivl, factor,
         reps, lapses, mod, flds, tags, mid) = row

        fields  = flds.split("\x1f")
        model   = models.get(str(mid), {})
        deck    = decks.get(str(did), {})
        mfields = model.get("flds", [])
        tmpls   = model.get("tmpls", [{}])
        tmpl    = tmpls[ord_] if ord_ < len(tmpls) else tmpls[0]
        fmap    = {f["name"]: fields[i] for i, f in enumerate(mfields) if i < len(fields)}

        batch.append((
            cid, nid,
            deck.get("name", "Default"),
            model.get("name", "Basic"),
            json.dumps(fmap),
            tmpl.get("qfmt", ""),
            tmpl.get("afmt", ""),
            model.get("css", ""),
            tags.strip(),
            queue, ctype, due, ivl, factor, reps, lapses, mod
        ))

    for b in batch:
        turso.execute("""
            INSERT OR REPLACE INTO cards
            (id, note_id, deck, model, fields, q_template, a_template,
             css, tags, queue, type, due, interval, factor, reps, lapses, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, b)

    turso.commit()
    return len(batch)


def pull_reviews(anki: sqlite3.Connection, turso) -> int:
    reviews = turso.execute(
        "SELECT id, card_id, rating, reviewed_at FROM review_log WHERE synced_to_anki=0"
    ).fetchall()

    if not reviews:
        return 0

    synced_ids = []
    now = int(time.time())

    for rev_id, card_id, rating, reviewed_at in reviews:
        card = anki.execute(
            "SELECT queue, type, due, ivl, factor, reps, lapses FROM cards WHERE id=?",
            (card_id,)
        ).fetchone()

        if not card:
            synced_ids.append(rev_id)
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

        today   = get_today_offset(anki)
        new_due = today + new_ivl if new_queue == 2 else now + 600

        anki.execute("""
            UPDATE cards SET queue=?, type=2, due=?, ivl=?, factor=?, reps=?, lapses=?, mod=?
            WHERE id=?
        """, (new_queue, new_due, new_ivl, new_factor, new_reps, new_lapses, now, card_id))

        anki.execute("""
            INSERT OR IGNORE INTO revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type)
            VALUES (?, ?, -1, ?, ?, ?, ?, ?, 1)
        """, (reviewed_at * 1000, card_id, rating, new_ivl, ivl, new_factor, 60000))

        synced_ids.append(rev_id)

    anki.commit()

    for rev_id in synced_ids:
        turso.execute("UPDATE review_log SET synced_to_anki=1 WHERE id=?", (rev_id,))
    turso.commit()

    return len(synced_ids)


def run_sync(show_result=True):
    try:
        import libsql_experimental as libsql
    except ImportError:
        tooltip("AnkiReverse : libsql_experimental non installé.\nFais : pip install libsql-experimental")
        return

    env = load_env()
    if not env.get("TURSO_URL") or not env.get("TURSO_TOKEN"):
        tooltip(f"AnkiReverse : fichier .env introuvable ou incomplet\n({ENV_FILE})")
        return

    if not mw.pm.name:
        return

    anki_db = Path.home() / f"Library/Application Support/Anki2/{mw.pm.name}/collection.anki2"
    if not anki_db.exists():
        tooltip(f"AnkiReverse : collection introuvable : {anki_db}")
        return

    try:
        turso = libsql.connect(database=env["TURSO_URL"], auth_token=env["TURSO_TOKEN"])
        anki  = sqlite3.connect(str(anki_db))

        pulled = pull_reviews(anki, turso)
        pushed = push_cards(anki, turso)

        anki.close()

        if show_result:
            msg = f"AnkiReverse sync OK\n↓ {pulled} révisions importées\n↑ {pushed} cartes exportées"
            tooltip(msg, period=4000)

    except Exception as e:
        tooltip(f"AnkiReverse sync erreur : {e}")


def sync_in_background(show_result=True):
    t = threading.Thread(target=run_sync, args=(show_result,), daemon=True)
    t.start()


# ── Hooks ─────────────────────────────────────────────────────────────────────

def on_profile_open():
    """Sync au démarrage (sans popup si tout va bien)."""
    sync_in_background(show_result=False)


def on_profile_close():
    """Sync à la fermeture — bloquant pour ne pas perdre de données."""
    run_sync(show_result=False)


gui_hooks.profile_did_open.append(on_profile_open)
gui_hooks.profile_will_close.append(on_profile_close)


# ── Menu Tools ────────────────────────────────────────────────────────────────

from aqt.qt import QAction

def add_menu_action():
    action = QAction("AnkiReverse — Sync maintenant", mw)
    action.triggered.connect(lambda: sync_in_background(show_result=True))
    mw.form.menuTools.addAction(action)

gui_hooks.main_window_did_init.append(add_menu_action)

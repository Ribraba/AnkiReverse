"""
AnkiReverse Sync — Add-on Anki
Synchronise les cartes avec Turso à l'ouverture/fermeture d'Anki.
Utilise mw.col (API interne) pour éviter les conflits SQLite.
"""
import json
import time
from pathlib import Path

from aqt import mw, gui_hooks
from aqt.utils import tooltip
from aqt.qt import QAction

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


# ── Lecture de la collection via mw.col ───────────────────────────────────────

def collect_cards_data() -> list:
    """Lit les cartes depuis mw.col.db (thread principal)."""
    if not mw.col:
        return []

    rows = mw.col.db.execute("""
        SELECT c.id, c.nid, c.did, c.ord, c.queue, c.type,
               c.due, c.ivl, c.factor, c.reps, c.lapses, c.mod,
               n.flds, n.tags, n.mid
        FROM cards c
        JOIN notes n ON c.nid = n.id
    """).fetchall()

    models_json = mw.col.db.scalar("SELECT models FROM col")
    decks_json  = mw.col.db.scalar("SELECT decks FROM col")
    models = json.loads(models_json) if models_json else {}
    decks  = json.loads(decks_json)  if decks_json  else {}

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
    return batch


def apply_reviews_to_col(reviews: list) -> int:
    """Applique les révisions Turso via l'API Anki (thread principal)."""
    if not mw.col or not reviews:
        return 0

    applied = 0
    now = int(time.time())

    crt = mw.col.db.scalar("SELECT crt FROM col WHERE id=1") or 0
    row = mw.col.db.first("SELECT val FROM config WHERE key='rollover'")
    rollover = int(row[0]) if row else 4
    today = (now - rollover * 3600 - (crt - rollover * 3600)) // 86400

    for rev_id, card_id, rating, reviewed_at in reviews:
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

        mw.col.db.execute("""
            UPDATE cards SET queue=?, type=2, due=?, ivl=?, factor=?, reps=?, lapses=?, mod=?
            WHERE id=?
        """, new_queue, new_due, new_ivl, new_factor, new_reps, new_lapses, now, card_id)

        mw.col.db.execute("""
            INSERT OR IGNORE INTO revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type)
            VALUES (?, ?, -1, ?, ?, ?, ?, ?, 1)
        """, reviewed_at * 1000, card_id, rating, new_ivl, ivl, new_factor, 60000)

        applied += 1

    if applied:
        mw.col.save()

    return applied


# ── Tâche réseau (thread arrière-plan) ────────────────────────────────────────

def turso_sync_task(cards_data: list):
    """
    Tourne dans un thread arrière-plan.
    Retourne (reviews_to_apply, pushed_count, synced_ids).
    """
    try:
        import libsql_experimental as libsql
    except ImportError:
        return None, 0, [], "libsql_experimental non installé"

    env = load_env()
    if not env.get("TURSO_URL") or not env.get("TURSO_TOKEN"):
        return None, 0, [], f"Fichier .env introuvable ou incomplet ({ENV_FILE})"

    try:
        turso = libsql.connect(database=env["TURSO_URL"], auth_token=env["TURSO_TOKEN"])

        # Pull reviews depuis Turso
        reviews = turso.execute(
            "SELECT id, card_id, rating, reviewed_at FROM review_log WHERE synced_to_anki=0"
        ).fetchall()

        # Push cards vers Turso
        for b in cards_data:
            turso.execute("""
                INSERT OR REPLACE INTO cards
                (id, note_id, deck, model, fields, q_template, a_template,
                 css, tags, queue, type, due, interval, factor, reps, lapses, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, b)
        turso.commit()

        # Marquer les reviews comme traitées
        synced_ids = [r[0] for r in reviews]

        return reviews, len(cards_data), synced_ids, None

    except Exception as e:
        return None, 0, [], str(e)


def mark_synced_task(synced_ids: list):
    """Marque les reviews comme appliquées dans Turso (thread arrière-plan)."""
    if not synced_ids:
        return
    try:
        import libsql_experimental as libsql
        env = load_env()
        turso = libsql.connect(database=env["TURSO_URL"], auth_token=env["TURSO_TOKEN"])
        for rev_id in synced_ids:
            turso.execute("UPDATE review_log SET synced_to_anki=1 WHERE id=?", (rev_id,))
        turso.commit()
    except Exception:
        pass


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_sync(show_result=True):
    if not mw.col:
        return

    # 1. Lire les données Anki sur le thread principal
    cards_data = collect_cards_data()

    # 2. Lancer le réseau en arrière-plan
    def background():
        return turso_sync_task(cards_data)

    def on_done(future):
        reviews, pushed, synced_ids, error = future.result()

        if error:
            tooltip(f"AnkiReverse sync erreur : {error}")
            return

        # 3. Appliquer les reviews sur le thread principal
        applied = apply_reviews_to_col(reviews)

        # 4. Marquer comme traités dans Turso (arrière-plan)
        import threading
        threading.Thread(target=mark_synced_task, args=(synced_ids,), daemon=True).start()

        if show_result:
            tooltip(
                f"AnkiReverse sync OK\n↓ {applied} révisions importées\n↑ {pushed} cartes exportées",
                period=4000
            )

    mw.taskman.run_in_background(background, on_done)


# ── Hooks ─────────────────────────────────────────────────────────────────────

_menu_added = False

def on_profile_open():
    global _menu_added
    # Ajouter le menu une seule fois
    if not _menu_added:
        action = QAction("AnkiReverse — Sync maintenant", mw)
        action.triggered.connect(lambda: run_sync(show_result=True))
        mw.form.menuTools.addAction(action)
        _menu_added = True

    # Sync silencieux au démarrage
    run_sync(show_result=False)


def on_profile_close():
    run_sync(show_result=False)


gui_hooks.profile_did_open.append(on_profile_open)
gui_hooks.profile_will_close.append(on_profile_close)

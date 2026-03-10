"""
Sync bidirectionnel : Anki Desktop ↔ Turso
- Push : lit collection.anki2 → envoie les cartes dans Turso
- Pull : lit les révisions faites sur iPhone → applique à collection.anki2

Usage : python scripts/sync_anki_turso.py
"""
import json, sqlite3, time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
ANKI_DB = Path.home() / "Library/Application Support/Anki2/Ibrahim/collection.anki2"

env = {}
for line in ROOT.joinpath(".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

import libsql_experimental as libsql

turso = libsql.connect(database=env["TURSO_URL"], auth_token=env["TURSO_TOKEN"])

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_today_offset(anki: sqlite3.Connection) -> int:
    crt = anki.execute("SELECT crt FROM col WHERE id=1").fetchone()[0]
    row = anki.execute("SELECT val FROM config WHERE key='rollover'").fetchone()
    rollover = int(row[0]) if row else 4
    now = int(time.time())
    return (now - rollover * 3600 - (crt - rollover * 3600)) // 86400


def push_cards_to_turso(anki: sqlite3.Connection):
    """Exporte toutes les cartes Anki vers Turso."""
    today = get_today_offset(anki)
    now = int(time.time())

    rows = anki.execute("""
        SELECT c.id, c.nid, c.did, c.ord, c.queue, c.type,
               c.due, c.ivl, c.factor, c.reps, c.lapses, c.mod,
               n.flds, n.tags, n.mid,
               col.models, col.decks
        FROM cards c
        JOIN notes n ON c.nid = n.id
        JOIN col ON col.id = 1
    """).fetchall()

    models_raw = anki.execute("SELECT models FROM col").fetchone()
    decks_raw  = anki.execute("SELECT decks FROM col").fetchone()
    models = json.loads(models_raw[0]) if models_raw[0] else {}
    decks  = json.loads(decks_raw[0])  if decks_raw[0]  else {}

    batch = []
    for row in rows:
        (cid, nid, did, ord_, queue, ctype, due, ivl, factor,
         reps, lapses, mod, flds, tags, mid, _, __) = row

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
    print(f"[push] {len(batch)} cartes synchronisées vers Turso")


def pull_reviews_from_turso(anki: sqlite3.Connection):
    """Lit les révisions faites sur iPhone et les applique à Anki."""
    reviews = turso.execute(
        "SELECT id, card_id, rating, reviewed_at FROM review_log WHERE synced_to_anki=0"
    ).fetchall()

    if not reviews:
        print("[pull] Aucune révision à synchroniser")
        return

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

        # Algorithme de scheduling simplifié (SM-2 like)
        # rating: 1=again, 2=hard, 3=good, 4=easy
        new_reps = reps + 1
        new_lapses = lapses + (1 if rating == 1 else 0)

        if rating == 1:  # Again
            new_ivl = 1
            new_factor = max(1300, factor - 200)
            new_queue = 1  # learning
        elif rating == 2:  # Hard
            new_ivl = max(1, int(ivl * 1.2))
            new_factor = max(1300, factor - 150)
            new_queue = 2
        elif rating == 3:  # Good
            new_ivl = max(1, int(ivl * factor / 1000))
            new_factor = factor
            new_queue = 2
        else:  # Easy
            new_ivl = max(1, int(ivl * factor / 1000 * 1.3))
            new_factor = factor + 150
            new_queue = 2

        today = get_today_offset(anki)
        new_due = today + new_ivl if new_queue == 2 else now + 600

        anki.execute("""
            UPDATE cards SET queue=?, type=2, due=?, ivl=?, factor=?, reps=?, lapses=?, mod=?
            WHERE id=?
        """, (new_queue, new_due, new_ivl, new_factor, new_reps, new_lapses, now, card_id))

        # Ajoute dans revlog Anki
        anki.execute("""
            INSERT OR IGNORE INTO revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type)
            VALUES (?, ?, -1, ?, ?, ?, ?, ?, 1)
        """, (reviewed_at * 1000, card_id, rating, new_ivl, ivl, new_factor, 60000))

        synced_ids.append(rev_id)

    anki.commit()

    # Marque comme synchronisés dans Turso
    for rev_id in synced_ids:
        turso.execute("UPDATE review_log SET synced_to_anki=1 WHERE id=?", (rev_id,))
    turso.commit()

    print(f"[pull] {len(synced_ids)} révisions appliquées à Anki")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Connexion à {ANKI_DB}")
    anki = sqlite3.connect(ANKI_DB)
    anki.row_factory = sqlite3.Row

    pull_reviews_from_turso(anki)
    push_cards_to_turso(anki)

    anki.close()
    print("Sync terminé.")

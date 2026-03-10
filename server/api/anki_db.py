"""
Lecture de la base de données Anki (SQLite .anki2)
Le schéma est documenté : https://github.com/ankidroid/Anki-Android/wiki/Database-Structure
"""
import json
import time
import aiosqlite
from pathlib import Path
from typing import Optional


def find_collection(data_path: str) -> Optional[Path]:
    """Trouve le fichier collection.anki2 dans le répertoire de données."""
    base = Path(data_path)
    # Le sync server officiel stocke les collections dans {data_path}/{username}/collection.anki2
    for path in base.rglob("collection.anki2"):
        return path
    return None


async def get_due_counts(db_path: Path) -> dict:
    """
    Retourne le nombre de cartes dues aujourd'hui.
    - new: nouvelles cartes
    - learning: en cours d'apprentissage
    - review: à réviser
    """
    today = _get_today_offset(db_path)

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Nouvelles cartes (queue=0, type=0)
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM cards WHERE queue = 0"
        )
        row = await cursor.fetchone()
        new_count = row["count"]

        # En apprentissage (queue=1 ou 3) dues maintenant
        now = int(time.time())
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM cards WHERE queue IN (1, 3) AND due <= ?",
            (now,),
        )
        row = await cursor.fetchone()
        learning_count = row["count"]

        # Révisions dues (queue=2, due <= today en jours)
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM cards WHERE queue = 2 AND due <= ?",
            (today,),
        )
        row = await cursor.fetchone()
        review_count = row["count"]

    return {
        "new": new_count,
        "learning": learning_count,
        "review": review_count,
        "total": new_count + learning_count + review_count,
    }


async def get_due_cards(db_path: Path, limit: int = 20) -> list[dict]:
    """
    Retourne les cartes dues avec leur contenu (question/réponse).
    Les champs sont séparés par le caractère 0x1f dans la DB.
    """
    today = _get_today_offset(db_path)
    now = int(time.time())

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT
                c.id, c.nid, c.did, c.ord, c.type, c.queue,
                c.due, c.ivl, c.factor, c.reps, c.lapses,
                n.flds, n.tags, n.mid,
                col.models, col.decks
            FROM cards c
            JOIN notes n ON c.nid = n.id
            JOIN col ON col.id = 1
            WHERE
                (c.queue = 0)
                OR (c.queue IN (1, 3) AND c.due <= ?)
                OR (c.queue = 2 AND c.due <= ?)
            ORDER BY c.due ASC
            LIMIT ?
            """,
            (now, today, limit),
        )
        rows = await cursor.fetchall()

    cards = []
    for row in rows:
        models = json.loads(row["models"])
        decks = json.loads(row["decks"])

        # Champs séparés par 0x1f
        fields = row["flds"].split("\x1f")

        model = models.get(str(row["mid"]), {})
        deck = decks.get(str(row["did"]), {})
        model_fields = model.get("flds", [])

        # Associe nom de champ → valeur
        field_map = {
            f["name"]: fields[i]
            for i, f in enumerate(model_fields)
            if i < len(fields)
        }

        # Question = premier champ, Réponse = second champ (modèle Basic)
        templates = model.get("tmpls", [{}])
        template = templates[row["ord"]] if row["ord"] < len(templates) else templates[0]

        cards.append(
            {
                "id": row["id"],
                "deck": deck.get("name", "Unknown"),
                "model": model.get("name", "Unknown"),
                "fields": field_map,
                "question_template": template.get("qfmt", ""),
                "answer_template": template.get("afmt", ""),
                "css": model.get("css", ""),
                "tags": row["tags"].strip().split(),
                "type": row["type"],
                "queue": row["queue"],
                "interval": row["ivl"],
                "reps": row["reps"],
                "lapses": row["lapses"],
            }
        )

    return cards


async def get_decks(db_path: Path) -> list[dict]:
    """Retourne la liste des decks."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT decks FROM col WHERE id = 1")
        row = await cursor.fetchone()

    decks = json.loads(row["decks"])
    return [
        {"id": did, "name": d["name"], "description": d.get("desc", "")}
        for did, d in decks.items()
        if d.get("name") != "Default" or len(decks) == 1
    ]


def _get_today_offset(db_path: Path) -> int:
    """
    Anki stocke les dates de révision comme un offset en jours depuis la création.
    Calcule le jour courant dans le système d'Anki.
    """
    import sqlite3

    with sqlite3.connect(db_path) as db:
        crt = db.execute("SELECT crt FROM col WHERE id = 1").fetchone()[0]
        # Anki 2.1.50+ stocke la config dans une table séparée
        row = db.execute("SELECT val FROM config WHERE key = 'rollover'").fetchone()
        rollover = int(row[0]) if row else 4  # défaut : 4h du matin

    now = int(time.time())
    # Ajuste pour le rollover (les nouvelles cartes du jour apparaissent après rollover)
    adjusted_now = now - rollover * 3600
    adjusted_crt = crt - rollover * 3600

    return (adjusted_now - adjusted_crt) // 86400

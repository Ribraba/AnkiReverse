"""
Initialise le schéma Turso. À lancer une seule fois.
Usage : python scripts/init_turso.py
"""
import os, sys
from pathlib import Path

# Charge .env
env = {}
for line in Path(__file__).parent.parent.joinpath(".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

import libsql_experimental as libsql

conn = libsql.connect(
    database=env["TURSO_URL"],
    auth_token=env["TURSO_TOKEN"],
)

schema = """
CREATE TABLE IF NOT EXISTS cards (
    id          INTEGER PRIMARY KEY,
    note_id     INTEGER NOT NULL,
    deck        TEXT NOT NULL,
    model       TEXT NOT NULL,
    fields      TEXT NOT NULL,
    q_template  TEXT NOT NULL,
    a_template  TEXT NOT NULL,
    css         TEXT DEFAULT '',
    tags        TEXT DEFAULT '',
    queue       INTEGER NOT NULL,
    type        INTEGER NOT NULL,
    due         INTEGER NOT NULL,
    interval    INTEGER DEFAULT 0,
    factor      INTEGER DEFAULT 2500,
    reps        INTEGER DEFAULT 0,
    lapses      INTEGER DEFAULT 0,
    updated_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS review_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id         INTEGER NOT NULL,
    rating          INTEGER NOT NULL,
    reviewed_at     INTEGER NOT NULL,
    synced_to_anki  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    endpoint    TEXT PRIMARY KEY,
    data        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_meta (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
"""

for statement in schema.strip().split(";"):
    s = statement.strip()
    if s:
        conn.execute(s)

conn.commit()
print("Schéma Turso initialisé avec succès.")

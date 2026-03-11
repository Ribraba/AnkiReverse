"""
AnkiReverse Sync — Add-on Anki 2.1.26
- mw.col.db pour lire Anki (pas de verrou SQLite)
- urllib pour Turso HTTP API (pas de dépendance externe)
- Ne pousse que les cartes modifiées depuis le dernier sync
"""
import json
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path

from aqt import mw, gui_hooks
from aqt.qt import (
    QAction, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QPushButton, Qt
)

ENV_FILE   = Path.home() / "Documents/Projets/CODE/AnkiReverse/.env"
STAMP_FILE = Path.home() / "Library/Application Support/Anki2/addons21/ankireverse_sync/last_sync.txt"
LOG_FILE   = Path.home() / "Library/Application Support/Anki2/addons21/ankireverse_sync/sync.log"

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(str(LOG_FILE), "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


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


def get_last_sync() -> int:
    try:
        return int(STAMP_FILE.read_text().strip())
    except Exception:
        return 0


def save_last_sync():
    STAMP_FILE.write_text(str(int(time.time())))


def turso_base_url(env: dict) -> str:
    return env.get("TURSO_URL", "").replace("libsql://", "https://")


# ── Turso HTTP API ─────────────────────────────────────────────────────────────

def turso_query(base_url: str, token: str, statements: list) -> list:
    if not statements:
        return []
    payload = [{"type": "execute", "stmt": s} for s in statements]
    payload.append({"type": "close"})
    body = json.dumps({"requests": payload}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/v2/pipeline",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [r["response"].get("result", {}) for r in data.get("results", []) if r.get("type") == "ok"]


def arg(v):
    if v is None:     return {"type": "null",    "value": None}
    if isinstance(v, int):   return {"type": "integer", "value": str(v)}
    if isinstance(v, float): return {"type": "float",   "value": str(v)}
    return {"type": "text", "value": str(v)}


# ── Lecture Anki ──────────────────────────────────────────────────────────────

def collect_changed_cards(since: int) -> list:
    """Cartes actives (non suspendues) modifiées depuis `since`."""
    rows = mw.col.db.all("""
        SELECT c.id, c.nid, c.did, c.ord, c.queue, c.type,
               c.due, c.ivl, c.factor, c.reps, c.lapses, c.mod,
               n.flds, n.tags, n.mid
        FROM cards c JOIN notes n ON c.nid = n.id
        WHERE c.queue >= 0
          AND (c.mod > ? OR n.mod > ?)
    """, since, since)

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
            "q": tmpl.get("qfmt", ""), "a": tmpl.get("afmt", ""),
            "css": model.get("css", ""), "tags": tags.strip(),
            "queue": queue, "type": ctype, "due": due,
            "ivl": ivl, "factor": factor, "reps": reps, "lapses": lapses, "mod": mod,
        })
    return batch


def apply_reviews(reviews: list) -> int:
    if not reviews:
        return 0
    now = int(time.time())
    crt  = mw.col.db.scalar("SELECT crt FROM col WHERE id=1") or 0
    rrow = mw.col.db.first("SELECT val FROM config WHERE key='rollover'")
    rollover = int(rrow[0]) if rrow else 4
    today = (now - rollover * 3600 - (crt - rollover * 3600)) // 86400

    applied = 0
    for card_id, rating, reviewed_at in reviews:
        card = mw.col.db.first(
            "SELECT queue, type, due, ivl, factor, reps, lapses FROM cards WHERE id=?", card_id)
        if not card:
            continue
        queue, ctype, due, ivl, factor, reps, lapses = card
        new_reps = reps + 1
        new_lapses = lapses + (1 if rating == 1 else 0)
        if   rating == 1: new_ivl, new_factor, new_queue = 1, max(1300, factor-200), 1
        elif rating == 2: new_ivl, new_factor, new_queue = max(1,int(ivl*1.2)), max(1300,factor-150), 2
        elif rating == 3: new_ivl, new_factor, new_queue = max(1,int(ivl*factor/1000)), factor, 2
        else:             new_ivl, new_factor, new_queue = max(1,int(ivl*factor/1000*1.3)), factor+150, 2
        new_due = today + new_ivl if new_queue == 2 else now + 600
        mw.col.db.execute(
            "UPDATE cards SET queue=?,type=2,due=?,ivl=?,factor=?,reps=?,lapses=?,mod=? WHERE id=?",
            new_queue, new_due, new_ivl, new_factor, new_reps, new_lapses, now, card_id)
        mw.col.db.execute(
            "INSERT OR IGNORE INTO revlog(id,cid,usn,ease,ivl,lastIvl,factor,time,type) VALUES(?,?,-1,?,?,?,?,?,1)",
            reviewed_at*1000, card_id, rating, new_ivl, ivl, new_factor, 60000)
        applied += 1
    if applied:
        try: mw.col.save()
        except Exception: pass
    return applied


# ── Tâche réseau ──────────────────────────────────────────────────────────────

def turso_sync_task(cards: list, env: dict):
    base  = turso_base_url(env)
    token = env.get("TURSO_TOKEN", "")
    log(f"turso_sync_task: base_url={base}")

    # Pull reviews
    log("turso_sync_task: pull reviews...")
    res = turso_query(base, token, [{"sql": "SELECT card_id, rating, reviewed_at FROM review_log WHERE synced_to_anki=0"}])
    reviews = []
    if res:
        for row in res[0].get("rows", []):
            reviews.append((int(row[0]["value"]), int(row[1]["value"]), int(row[2]["value"])))
    log(f"turso_sync_task: {len(reviews)} reviews trouvées")

    # Push cards modifiées (batch 100)
    log(f"turso_sync_task: push {len(cards)} cartes...")
    stmts = []
    for c in cards:
        stmts.append({"sql": """INSERT OR REPLACE INTO cards
            (id,note_id,deck,model,fields,q_template,a_template,css,tags,queue,type,due,interval,factor,reps,lapses,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            "args": [arg(v) for v in (c["id"],c["nid"],c["deck"],c["model"],c["fields"],
                c["q"],c["a"],c["css"],c["tags"],c["queue"],c["type"],c["due"],
                c["ivl"],c["factor"],c["reps"],c["lapses"],c["mod"])]})
        if len(stmts) == 500:
            turso_query(base, token, stmts); stmts = []
    if stmts:
        turso_query(base, token, stmts)

    # Marquer reviews traitées
    if reviews:
        turso_query(base, token, [
            {"sql": "UPDATE review_log SET synced_to_anki=1 WHERE card_id=? AND reviewed_at=?",
             "args": [arg(cid), arg(rat)]} for cid, _, rat in reviews])

    return reviews, len(cards)


# ── Fenêtre de progression ────────────────────────────────────────────────────

class SyncDialog(QDialog):
    def __init__(self):
        super().__init__(mw)
        self.setWindowTitle("AnkiReverse")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint)
        self.setMinimumWidth(320)
        self.setModal(False)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self._label = QLabel("Synchronisation en cours...")
        self._label.setAlignment(Qt.AlignCenter)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)   # indéterminé (animation)
        self._bar.setTextVisible(False)

        layout.addWidget(self._label)
        layout.addWidget(self._bar)
        self.setLayout(layout)

    def set_done(self, pushed: int, applied: int):
        self._bar.setRange(0, 1)
        self._bar.setValue(1)
        msg = f"↑  {pushed} cartes exportées"
        if applied:
            msg += f"\n↓  {applied} révisions iPhone importées"
        self._label.setText(msg)

        # Bouton OK
        btn = QPushButton("OK")
        btn.clicked.connect(self.accept)
        self.layout().addWidget(btn)

    def set_error(self, message: str):
        self._bar.hide()
        self._label.setText(f"Erreur :\n{message}")
        btn = QPushButton("OK")
        btn.clicked.connect(self.accept)
        self.layout().addWidget(btn)


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_sync(show_result=True):
    if not mw.col:
        return

    env = load_env()
    if not env.get("TURSO_URL") or not env.get("TURSO_TOKEN"):
        if show_result:
            dlg = SyncDialog()
            dlg.set_error(f"Fichier .env introuvable :\n{ENV_FILE}")
            dlg.exec_()
        return

    try:
        since = get_last_sync()
        log(f"Lecture cartes modifiées depuis {since}")
        cards = collect_changed_cards(since)
        log(f"{len(cards)} cartes à envoyer")
    except Exception as e:
        log(f"ERREUR collect_changed_cards: {e}")
        if show_result:
            dlg = SyncDialog()
            dlg.set_error(str(e))
            dlg.exec_()
        return

    dlg = SyncDialog() if show_result else None
    if dlg:
        dlg.show()

    result_container = [None]
    error_container  = [None]

    def background():
        try:
            log("background: début turso_sync_task")
            result_container[0] = turso_sync_task(cards, env)
            log(f"background: terminé — {result_container[0][1]} cartes, {len(result_container[0][0])} reviews")
        except Exception as e:
            log(f"background ERREUR: {e}")
            error_container[0] = str(e)

    def check_done():
        if result_container[0] is None and error_container[0] is None:
            log("check_done: pas encore terminé, repoll dans 500ms")
            mw.progress.timer(500, check_done, False)
            return

        log("check_done: résultat reçu")
        if error_container[0]:
            if dlg:
                dlg.set_error(error_container[0])
            return

        reviews, pushed = result_container[0]
        try:
            applied = apply_reviews(reviews)
            log(f"apply_reviews: {applied} révisions appliquées")
        except Exception as e:
            log(f"apply_reviews ERREUR: {e}")
            applied = 0

        save_last_sync()

        if dlg:
            dlg.set_done(pushed, applied)

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
    mw.progress.timer(3000, lambda: run_sync(show_result=True), False)


def on_profile_close():
    if not mw.col:
        return
    env = load_env()
    if not env.get("TURSO_URL"):
        return
    try:
        cards = collect_changed_cards(get_last_sync())
        turso_sync_task(cards, env)
        save_last_sync()
    except Exception:
        pass


gui_hooks.profile_did_open.append(on_profile_open)
gui_hooks.profile_will_close.append(on_profile_close)

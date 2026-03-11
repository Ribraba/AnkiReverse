"""
AnkiReverse Sync — Add-on Anki 2.1.26
- mw.col.db pour lire Anki (pas de verrou SQLite)
- urllib pour Turso HTTP API (pas de dépendance externe)
- Pousse les cartes dues + les 7 prochains jours (révisions supplémentaires)
"""
import json
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path

from aqt import mw, gui_hooks
from aqt.qt import (
    QAction, QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget,
    QLabel, QProgressBar, QPushButton, QCheckBox, Qt
)

ENV_FILE      = Path.home() / "Documents/Projets/CODE/AnkiReverse/.env"
STAMP_FILE    = Path.home() / "Library/Application Support/Anki2/addons21/ankireverse_sync/last_sync.txt"
LOG_FILE      = Path.home() / "Library/Application Support/Anki2/addons21/ankireverse_sync/sync.log"
EXCLUDE_FILE  = Path.home() / "Library/Application Support/Anki2/addons21/ankireverse_sync/excluded_decks.json"

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

def get_today_offset() -> int:
    """Utilise l'API native Anki — pas de SQL pour éviter les quirks du wrapper DB."""
    crt      = int(mw.col.crt)
    rollover = int(mw.col.conf.get("rollover", 4))
    return int((time.time() - rollover * 3600 - (crt - rollover * 3600)) // 86400)


def collect_due_cards(ahead_days: int = 7) -> list:
    """
    Cartes dues aujourd'hui + dans les <ahead_days> prochains jours.
    - queue=0 : nouvelles cartes
    - queue=1 : en apprentissage
    - queue=2 : révisions (due <= today + ahead_days)
    """
    today = get_today_offset()

    rows = mw.col.db.all("""
        SELECT c.id, c.nid, c.did, c.ord, c.queue, c.type,
               c.due, c.ivl, c.factor, c.reps, c.lapses, c.mod,
               n.flds, n.tags, n.mid
        FROM cards c JOIN notes n ON c.nid = n.id
        WHERE (c.queue = 0)
           OR (c.queue = 1)
           OR (c.queue = 2 AND c.due <= ?)
    """, int(today + ahead_days))

    # API native Anki (disponible depuis 2.0.x)
    models   = {str(m["id"]): m for m in mw.col.models.all()}
    decks    = {str(d["id"]): d for d in mw.col.decks.all()}
    excluded = load_excluded_decks()

    batch = []
    for row in rows:
        cid, nid, did, ord_, queue, ctype, due, ivl, factor, reps, lapses, mod, flds, tags, mid = row
        fields  = flds.split("\x1f")
        model     = models.get(str(mid), {})
        deck      = decks.get(str(did), {})
        deck_name = deck.get("name", "Default")
        if deck_name in excluded:
            continue
        mfields = model.get("flds", [])
        tmpls   = model.get("tmpls", [{}])
        tmpl    = tmpls[ord_] if ord_ < len(tmpls) else tmpls[0]
        fmap    = {f["name"]: fields[i] for i, f in enumerate(mfields) if i < len(fields)}
        batch.append({
            "id": cid, "nid": nid,
            "deck": deck_name,
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
    now   = int(time.time())
    today = get_today_offset()

    applied = 0
    for card_id, rating, reviewed_at in reviews:
        row = mw.col.db.first(
            "SELECT queue, type, due, ivl, factor, reps, lapses FROM cards WHERE id=?", card_id)
        if not row:
            continue
        # db.first() returns a list in Anki 2.1.26
        queue, ctype, due, ivl, factor, reps, lapses = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
        new_reps   = reps + 1
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

def turso_sync_task(cards: list, env: dict, progress_cb=None):
    base  = turso_base_url(env)
    token = env.get("TURSO_TOKEN", "")
    log(f"turso_sync_task: base_url={base}")

    # 1. Pull reviews
    if progress_cb: progress_cb("Récupération des révisions iPhone...")
    log("turso_sync_task: pull reviews...")
    res = turso_query(base, token, [{"sql": "SELECT card_id, rating, reviewed_at FROM review_log WHERE synced_to_anki=0"}])
    reviews = []
    if res:
        for row in res[0].get("rows", []):
            reviews.append((int(row[0]["value"]), int(row[1]["value"]), int(row[2]["value"])))
    log(f"turso_sync_task: {len(reviews)} reviews trouvées")

    # 2. Push cards en batch de 500
    total   = len(cards)
    sent    = 0
    stmts   = []
    batch_n = 0
    nb_batches = max(1, (total + 499) // 500)

    for c in cards:
        stmts.append({"sql": """INSERT OR REPLACE INTO cards
            (id,note_id,deck,model,fields,q_template,a_template,css,tags,queue,type,due,interval,factor,reps,lapses,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            "args": [arg(v) for v in (c["id"],c["nid"],c["deck"],c["model"],c["fields"],
                c["q"],c["a"],c["css"],c["tags"],c["queue"],c["type"],c["due"],
                c["ivl"],c["factor"],c["reps"],c["lapses"],c["mod"])]})
        if len(stmts) == 500:
            batch_n += 1
            sent    += len(stmts)
            if progress_cb:
                progress_cb(f"Envoi des cartes... ({sent}/{total})", sent, total)
            log(f"turso_sync_task: batch {batch_n}/{nb_batches} — {sent}/{total} cartes")
            turso_query(base, token, stmts)
            stmts = []

    if stmts:
        batch_n += 1
        sent    += len(stmts)
        if progress_cb:
            progress_cb(f"Envoi des cartes... ({sent}/{total})", sent, total)
        log(f"turso_sync_task: batch {batch_n}/{nb_batches} — {sent}/{total} cartes")
        turso_query(base, token, stmts)

    # 3. Marquer reviews traitées
    if reviews:
        if progress_cb: progress_cb("Mise à jour des révisions...")
        turso_query(base, token, [
            {"sql": "UPDATE review_log SET synced_to_anki=1 WHERE card_id=? AND reviewed_at=?",
             "args": [arg(cid), arg(rat)]} for cid, _, rat in reviews])

    # 4. Sauvegarder today_offset dans Turso (pour la PWA)
    today = get_today_offset()
    turso_query(base, token, [{
        "sql": "INSERT OR REPLACE INTO sync_meta(key, value) VALUES('today_offset', ?)",
        "args": [arg(today)]
    }])

    log(f"turso_sync_task: terminé — {sent} cartes, {len(reviews)} reviews")
    return reviews, sent


# ── Fenêtre de progression ────────────────────────────────────────────────────

class SyncDialog(QDialog):
    def __init__(self):
        super().__init__(mw)
        self.setWindowTitle("AnkiReverse — Synchronisation")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint)
        self.setMinimumWidth(360)
        self.setModal(False)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        self._step = QLabel("Démarrage...")
        self._step.setAlignment(Qt.AlignLeft)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)   # indéterminé
        self._bar.setTextVisible(False)

        layout.addWidget(self._step)
        layout.addWidget(self._bar)
        self.setLayout(layout)

    def set_step(self, text: str, value: int = -1, maximum: int = -1):
        self._step.setText(text)
        if maximum > 0:
            self._bar.setRange(0, maximum)
            self._bar.setValue(value)
        else:
            self._bar.setRange(0, 0)   # reste indéterminé

    def set_done(self, pushed: int, applied: int):
        self._bar.setRange(0, 1)
        self._bar.setValue(1)
        lines = [f"✓  {pushed} cartes synchronisées"]
        if applied:
            lines.append(f"✓  {applied} révisions iPhone importées")
        self._step.setText("\n".join(lines))

        btn = QPushButton("OK")
        btn.clicked.connect(self.accept)
        self.layout().addWidget(btn)

    def set_error(self, message: str):
        self._bar.hide()
        self._step.setText(f"Erreur :\n{message}")
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
        cards = collect_due_cards(ahead_days=7)
        log(f"{len(cards)} cartes à envoyer (dues + 7 jours)")
    except Exception as e:
        log(f"ERREUR collect_due_cards: {e}")
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

    def on_progress(text, value=-1, maximum=-1):
        # Appelé depuis le thread background — Qt n'est pas thread-safe,
        # on stocke juste le message et check_done l'affichera
        progress_container[0] = (text, value, maximum)

    progress_container = [None]

    def background():
        try:
            log(f"background: début turso_sync_task ({len(cards)} cartes)")
            result_container[0] = turso_sync_task(cards, env, progress_cb=on_progress)
            log(f"background: terminé — {result_container[0][1]} cartes, {len(result_container[0][0])} reviews")
        except Exception as e:
            log(f"background ERREUR: {e}")
            error_container[0] = str(e)

    def check_done():
        # Mise à jour du label si progression disponible
        if dlg and progress_container[0]:
            text, val, maxi = progress_container[0]
            dlg.set_step(text, val, maxi)
            progress_container[0] = None

        if result_container[0] is None and error_container[0] is None:
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


# ── Gestion des decks exclus ──────────────────────────────────────────────────

def load_excluded_decks() -> set:
    try:
        return set(json.loads(EXCLUDE_FILE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_excluded_decks(decks: set):
    EXCLUDE_FILE.write_text(json.dumps(sorted(decks), ensure_ascii=False), encoding="utf-8")


class DeckFilterDialog(QDialog):
    def __init__(self):
        super().__init__(mw)
        self.setWindowTitle("AnkiReverse — Decks à synchroniser")
        self.setMinimumWidth(380)
        self.setMinimumHeight(400)

        excluded = load_excluded_decks()
        all_decks = sorted(d["name"] for d in mw.col.decks.all() if "::" not in d["name"] or True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Décochez les decks à exclure de la synchronisation :"))

        # Boutons tout sélectionner / tout déselectionner
        sel_row = QHBoxLayout()
        btn_all = QPushButton("Tout sélectionner")
        btn_none = QPushButton("Tout déselectionner")
        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_none.clicked.connect(lambda: self._set_all(False))
        sel_row.addWidget(btn_all)
        sel_row.addWidget(btn_none)
        layout.addLayout(sel_row)

        # Zone scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.NoFrame)
        container = QWidget()
        inner = QVBoxLayout(container)
        inner.setSpacing(4)

        self._checkboxes = {}
        for name in all_decks:
            cb = QCheckBox(name)
            cb.setChecked(name not in excluded)
            inner.addWidget(cb)
            self._checkboxes[name] = cb

        inner.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Boutons
        btn_row = QVBoxLayout()
        btn_save = QPushButton("Enregistrer")
        btn_save.clicked.connect(self._save)
        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _set_all(self, checked: bool):
        for cb in self._checkboxes.values():
            cb.setChecked(checked)

    def _save(self):
        excluded = {name for name, cb in self._checkboxes.items() if not cb.isChecked()}
        save_excluded_decks(excluded)
        self.accept()


# ── Hooks ─────────────────────────────────────────────────────────────────────

_menu_added = False

def on_profile_open():
    global _menu_added
    if not _menu_added:
        action_sync = QAction("AnkiReverse — Sync maintenant", mw)
        action_sync.triggered.connect(lambda: run_sync(show_result=True))
        mw.form.menuTools.addAction(action_sync)

        action_cfg = QAction("AnkiReverse — Choisir les decks", mw)
        action_cfg.triggered.connect(lambda: DeckFilterDialog().exec_())
        mw.form.menuTools.addAction(action_cfg)

        _menu_added = True
    mw.progress.timer(3000, lambda: run_sync(show_result=True), False)


def on_profile_close():
    if not mw.col:
        return
    env = load_env()
    if not env.get("TURSO_URL"):
        return
    try:
        cards = collect_due_cards(ahead_days=7)
        _, pushed = turso_sync_task(cards, env)
        save_last_sync()
        log(f"on_profile_close: {pushed} cartes synchronisées")
    except Exception as e:
        log(f"on_profile_close ERREUR: {e}")


gui_hooks.profile_did_open.append(on_profile_open)
gui_hooks.profile_will_close.append(on_profile_close)

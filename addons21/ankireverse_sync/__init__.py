"""
AnkiReverse Sync — Add-on Anki 2.1.26
Lance sync_anki_turso.py via subprocess (Python my_env) pour éviter
les conflits avec le Python gelé d'Anki.
"""
import threading
import subprocess
from pathlib import Path

from aqt import mw, gui_hooks
from aqt.utils import showInfo
from aqt.qt import QAction

# ── Chemins ───────────────────────────────────────────────────────────────────

PROJECT = Path.home() / "Documents/Projets/CODE/AnkiReverse"
SCRIPT  = PROJECT / "scripts/sync_anki_turso.py"

# Python du virtualenv my_env où libsql_experimental est installé
PYTHON  = PROJECT / "my_env/bin/python3"

# Fallback sur python3 système si my_env absent
if not PYTHON.exists():
    PYTHON = Path("/usr/bin/python3")


# ── Sync via subprocess ────────────────────────────────────────────────────────

def run_sync_subprocess():
    """Lance le script de sync et retourne (success, stdout, stderr)."""
    if not SCRIPT.exists():
        return False, "", f"Script introuvable : {SCRIPT}"
    if not PYTHON.exists():
        return False, "", f"Python introuvable : {PYTHON}"

    try:
        result = subprocess.run(
            [str(PYTHON), str(SCRIPT)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT)
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Timeout — vérifier la connexion réseau"
    except Exception as e:
        return False, "", str(e)


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_sync(show_result=True):
    result_container = [None]

    def background():
        result_container[0] = run_sync_subprocess()

    def check_done():
        if result_container[0] is None:
            # Pas encore terminé, on repoll dans 500ms (sur le thread principal)
            mw.progress.timer(500, check_done, False)
            return

        success, stdout, stderr = result_container[0]

        if not show_result:
            return

        if success:
            msg = "AnkiReverse — Sync terminée\n\n" + (stdout or "Aucun changement.")
            showInfo(msg, title="AnkiReverse")
        else:
            showInfo(f"AnkiReverse — Erreur :\n\n{stderr}", title="AnkiReverse")

    threading.Thread(target=background, daemon=True).start()
    # Timer créé sur le thread principal → safe
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

    run_sync(show_result=True)


def on_profile_close():
    # Sync synchrone bloquante à la fermeture
    run_sync_subprocess()


gui_hooks.profile_did_open.append(on_profile_open)
gui_hooks.profile_will_close.append(on_profile_close)

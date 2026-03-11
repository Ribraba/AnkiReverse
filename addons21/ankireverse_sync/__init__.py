"""
AnkiReverse Sync — Add-on Anki 2.1.26
Lance sync_anki_turso.py via subprocess pour éviter les conflits
avec le Python gelé d'Anki.
"""
import threading
import subprocess
import sys
from pathlib import Path

from aqt import mw, gui_hooks
from aqt.utils import showInfo
from aqt.qt import QAction

# ── Chemins ───────────────────────────────────────────────────────────────────

PROJECT = Path.home() / "Documents/Projets/CODE/AnkiReverse"
SCRIPT  = PROJECT / "scripts/sync_anki_turso.py"


def find_python() -> Path:
    """Cherche un Python avec libsql_experimental installé."""
    candidates = [
        PROJECT / "my_env/bin/python3",
        Path.home() / ".pyenv/shims/python3",
        Path("/usr/local/bin/python3"),
        Path("/opt/homebrew/bin/python3"),
        Path("/usr/bin/python3"),
    ]
    # Tester chaque candidat
    for p in candidates:
        if not p.exists():
            continue
        try:
            r = subprocess.run(
                [str(p), "-c", "import libsql_experimental"],
                capture_output=True, timeout=5
            )
            if r.returncode == 0:
                return p
        except Exception:
            continue
    return None


PYTHON = find_python()


# ── Sync via subprocess ────────────────────────────────────────────────────────

def run_sync_subprocess():
    """Lance le script de sync. Retourne (success, stdout, stderr)."""
    if not SCRIPT.exists():
        return False, "", f"Script introuvable :\n{SCRIPT}"

    if PYTHON is None:
        return False, "", (
            "Impossible de trouver un Python avec libsql_experimental.\n"
            "Lance dans ton terminal :\n"
            "  pip install libsql-experimental"
        )

    try:
        result = subprocess.run(
            [str(PYTHON), str(SCRIPT)],
            capture_output=True,
            timeout=60,
            cwd=str(PROJECT),
            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
        )
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        return result.returncode == 0, stdout, stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout (60s) — vérifier la connexion réseau"
    except Exception as e:
        return False, "", str(e)


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_sync(show_result=True):
    result_container = [None]

    def background():
        result_container[0] = run_sync_subprocess()

    def check_done():
        if result_container[0] is None:
            mw.progress.timer(500, check_done, False)
            return

        if not show_result:
            return

        success, stdout, stderr = result_container[0]
        if success:
            showInfo(stdout or "Sync terminée.", title="AnkiReverse ✓")
        else:
            showInfo(stderr or "Erreur inconnue.", title="AnkiReverse — Erreur")

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

    run_sync(show_result=True)


def on_profile_close():
    run_sync_subprocess()


gui_hooks.profile_did_open.append(on_profile_open)
gui_hooks.profile_will_close.append(on_profile_close)

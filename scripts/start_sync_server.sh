#!/bin/bash
# Lance le serveur de sync Anki officiel (Python package)
# Usage : ./scripts/start_sync_server.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# Charge les variables d'environnement
if [ -f "$ENV_FILE" ]; then
  export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

# Répertoire de données du sync server
DATA_DIR="$SCRIPT_DIR/.anki_data"
mkdir -p "$DATA_DIR"

echo "Démarrage du serveur de sync Anki sur http://localhost:27701"
echo "Utilisateur : ${SYNC_USER1%%:*}"
echo "Données stockées dans : $DATA_DIR"
echo ""

source "$SCRIPT_DIR/my_env/bin/activate"

SYNC_USER1="$SYNC_USER1" \
SYNC_BASE="$DATA_DIR" \
SYNC_PORT=27701 \
python -m anki.syncserver

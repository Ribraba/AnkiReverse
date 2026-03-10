#!/bin/bash
# Configure Anki Desktop pour utiliser notre serveur de sync local
# À exécuter une seule fois sur le Mac

SYNC_SERVER_URL="${1:-http://localhost:27701}"

echo "Configuration d'Anki pour utiliser : $SYNC_SERVER_URL"
echo ""
echo "Dans Anki Desktop :"
echo "  1. Ouvrez Anki"
echo "  2. Allez dans Préférences → Réseau"
echo "  3. Cochez 'Serveur de synchronisation personnalisé'"
echo "  4. Entrez : $SYNC_SERVER_URL"
echo "  5. Redémarrez Anki et synchronisez"
echo ""
echo "Ou via la variable d'environnement (méthode automatique) :"
echo ""

# Méthode via variable d'environnement (Anki 2.1.57+)
PLIST_PATH="$HOME/Library/LaunchAgents/net.ankiweb.anki.plist"

cat > /tmp/anki_sync_env.sh << EOF
# Ajoutez ces lignes dans ~/.zshrc ou ~/.zprofile
export ANKI_SYNC_SERVER="$SYNC_SERVER_URL"
EOF

echo "Ajoutez ceci dans votre ~/.zshrc :"
echo "  export ANKI_SYNC_SERVER=\"$SYNC_SERVER_URL\""
echo ""
echo "Ensuite redémarrez Anki depuis le terminal : open /Applications/Anki.app"

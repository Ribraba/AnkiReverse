# AnkiReverse

PWA pour réviser ses fiches Anki sur iPhone et Mac, avec notifications push.
Conçu pour remplacer AnkiMobile sans payer 30€ — fonctionne dans Safari comme une app native.

---

## Architecture

```
Anki Desktop (Mac)
      │
      ▼
scripts/sync_anki_turso.py   ← script Python à lancer sur Mac
      │
      ▼
   Turso (cloud SQLite)       ← base de données en ligne, tier gratuit
      │
      ▼
  Next.js PWA (Vercel)        ← interface de révision
      │
      ▼
   iPhone / Safari            ← installable sur l'écran d'accueil
```

### Comment ça marche ?

1. **Anki Desktop** stocke toutes tes cartes dans un fichier SQLite local (`collection.anki2`)
2. Le **script Python** lit ce fichier directement et pousse les cartes dues vers **Turso** (base cloud)
3. La **PWA Next.js** déployée sur Vercel interroge Turso via API pour afficher les cartes
4. Quand tu révises sur iPhone, la note (1-4) est enregistrée dans Turso
5. Au prochain lancement du script sur Mac, les révisions iPhone sont récupérées depuis Turso et appliquées dans Anki Desktop (algorithme SM-2)

---

## Fonctionnalités

- Révision des cartes dues avec algorithme SM-2 (identique à Anki)
- Filtrage par deck (sélection dans "Mes decks")
- Notifications push (rappel quotidien à 9h)
- Auth GitHub OAuth (accès personnel uniquement)
- Design sombre style macOS, police Neris, animations fluides
- Installable sur iPhone via Safari → Partager → Sur l'écran d'accueil

---

## Stack

| Composant | Technologie |
|-----------|-------------|
| Frontend | Next.js 16 App Router + Tailwind CSS v4 |
| Base de données | Turso (libSQL cloud, tier gratuit) |
| Auth | NextAuth.js + GitHub OAuth |
| Push | Web Push API + VAPID |
| Déploiement | Vercel (tier gratuit) |
| Sync Mac | Python + libsql_experimental |

---

## Structure du projet

```
AnkiReverse/
├── pwa/                          → Application Next.js (Vercel)
│   ├── src/app/                  → Pages (/, /review, /decks, /login)
│   ├── src/app/api/              → Routes API (counts, cards, review, decks)
│   ├── src/lib/                  → turso.ts, auth.ts, api.ts, push.ts
│   └── public/                   → manifest.json, icônes, fonts Neris
│
├── scripts/
│   ├── sync_anki_turso.py        → Sync bidirectionnel Anki ↔ Turso (à lancer sur Mac)
│   ├── init_turso.py             → Création des tables Turso (une seule fois)
│   └── generate_vapid.py         → Génère les clés VAPID pour les notifications
│
└── server/                       → Ancienne API FastAPI (non utilisée en prod)
```

---

## Installation complète

### Prérequis

- Anki Desktop installé sur Mac avec tes cartes
- Compte GitHub (pour l'OAuth)
- Compte Turso (gratuit) : https://turso.tech
- Compte Vercel (gratuit) : https://vercel.com

---

### Étape 1 — Turso (base de données cloud)

```bash
# Installer le CLI Turso
brew install tursodatabase/tap/turso
turso auth login

# Créer la base
turso db create ankireverse
turso db show ankireverse           # copie l'URL (libsql://...)
turso db tokens create ankireverse  # copie le token

# Initialiser les tables
pip install libsql-experimental
TURSO_URL="libsql://..." TURSO_TOKEN="..." python scripts/init_turso.py
```

---

### Étape 2 — GitHub OAuth

1. Va sur https://github.com/settings/developers → **New OAuth App**
2. **Homepage URL** : `https://ton-app.vercel.app`
3. **Authorization callback URL** : `https://ton-app.vercel.app/api/auth/callback/github`
4. Copie le **Client ID** et génère un **Client Secret**

---

### Étape 3 — Variables d'environnement

Crée `pwa/.env.local` :

```env
# Turso
TURSO_URL=libsql://ankireverse-xxx.turso.io
TURSO_TOKEN=eyJ...

# GitHub OAuth
GITHUB_ID=ton_client_id
GITHUB_SECRET=ton_client_secret

# NextAuth
NEXTAUTH_SECRET=une_chaine_aleatoire_longue   # openssl rand -base64 32
NEXTAUTH_URL=https://ton-app.vercel.app

# Accès restreint à toi uniquement
ALLOWED_EMAIL=ton@email.com

# VAPID (notifications push)
# Générer avec : python scripts/generate_vapid.py
NEXT_PUBLIC_VAPID_KEY=BxxxxPublicKey
VAPID_PRIVATE_KEY=xxxxPrivateKey
VAPID_EMAIL=mailto:ton@email.com
```

---

### Étape 4 — Déploiement sur Vercel

1. Push le code sur GitHub
2. Connecte le repo sur https://vercel.com → New Project
3. **Root Directory** : `pwa/`
4. Ajoute toutes les variables d'env dans Vercel → Settings → Environment Variables
5. Deploy

---

### Étape 5 — Sync Anki Desktop (Mac)

```bash
# Installer les dépendances Python
pip install libsql-experimental python-dotenv

# Créer un .env à la racine avec tes identifiants Turso
cp .env.example .env
# Remplis TURSO_URL et TURSO_TOKEN dans .env

# Lancer le sync (à faire avant/après chaque session de révision)
python scripts/sync_anki_turso.py
```

Le script trouve automatiquement ta collection Anki dans `~/Library/Application Support/Anki2/`.

**Workflow recommandé :**
- Lance `sync_anki_turso.py` **avant** de réviser sur iPhone → les cartes du jour sont chargées dans Turso
- Révise sur iPhone / Vercel
- Lance `sync_anki_turso.py` **après** → les notes sont appliquées dans Anki Desktop

**Automatiser avec cron (optionnel) :**
```bash
# Sync automatique à 8h chaque matin
crontab -e
0 8 * * * /usr/bin/python3 /chemin/vers/scripts/sync_anki_turso.py
```

**À faire sur Anki Desktop :**
- Rien de spécial — continue à utiliser Anki normalement (add-ons, Beautiful Anki, etc.)
- Ne pas lancer de sync Anki natif vers AnkiWeb pendant une session iPhone (risque de conflit) — utilise uniquement le script Python pour la synchro

---

### Étape 6 — Installer la PWA sur iPhone

1. Ouvre l'URL Vercel dans **Safari** (pas Chrome)
2. Connecte-toi avec ton compte GitHub
3. Appuie sur le bouton **Partager** (carré avec flèche) → **Sur l'écran d'accueil**
4. L'app s'installe comme une application native avec l'icône cerveau

---

## Sync bidirectionnel — détail technique

Le script `sync_anki_turso.py` fonctionne en deux passes :

1. **Turso → Anki Desktop** : lit la table `review_log` (révisions faites sur iPhone), applique les résultats dans le SQLite local d'Anki avec SM-2 (mise à jour de `due`, `ivl`, `factor`, `reps`, `lapses`), puis marque les révisions comme appliquées
2. **Anki Desktop → Turso** : lit les cartes dues dans le SQLite local et les pousse dans la table `cards` de Turso

---

## Notifications push

Les notifications nécessitent :
- D'avoir cliqué "Activer" dans l'app (Safari iOS 16.4+ requis)
- Les clés VAPID configurées dans les variables d'environnement Vercel
- Le cron Vercel configuré sur `/api/push/notify` pour 9h chaque matin

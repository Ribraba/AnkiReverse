# AnkiReverse

PWA pour réviser ses fiches Anki sur iPhone et Mac, avec notifications push.

## Architecture

```
Anki Desktop (Mac)
      │
      ▼
scripts/sync_anki_turso.py   ← sync bidirectionnel
      │
      ▼
   Turso (cloud SQLite)
      │
      ▼
  Next.js PWA (Vercel)        ← interface de révision
      │
      ▼
   iPhone / Safari
```

## Fonctionnalités

- Révision des cartes dues avec algorithme SM-2
- Filtrage par deck
- Notifications push (rappel quotidien à 9h)
- Auth GitHub OAuth (accès personnel uniquement)
- Design sombre, police Neris, animations fluides
- 100% offline-ready (PWA installable)

## Stack

- **Frontend** : Next.js 16 App Router + Tailwind CSS v4 + Lucide icons
- **Base de données** : Turso (libSQL cloud)
- **Auth** : NextAuth.js + GitHub OAuth
- **Push** : Web Push API + VAPID
- **Déploiement** : Vercel
- **Sync** : Python + libsql_experimental

## Structure

```
pwa/          → application Next.js (déployée sur Vercel)
scripts/      → scripts Python de synchronisation (Mac)
server/       → ancienne API FastAPI (remplacée par les routes Next.js)
```

## Installation

### 1. Turso

```bash
turso db create ankireverse
turso db tokens create ankireverse
python scripts/init_turso.py
```

### 2. Variables d'environnement (`pwa/.env.local`)

```
TURSO_URL=libsql://...
TURSO_TOKEN=...
GITHUB_ID=...
GITHUB_SECRET=...
NEXTAUTH_SECRET=...
NEXTAUTH_URL=https://ton-app.vercel.app
ALLOWED_EMAIL=ton@email.com
NEXT_PUBLIC_VAPID_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_EMAIL=mailto:ton@email.com
```

### 3. Sync Anki → Turso (Mac)

```bash
python scripts/sync_anki_turso.py
```

### 4. Déploiement

```bash
cd pwa
git push origin main   # Vercel déploie automatiquement
```

## Sync bidirectionnel

Le script `sync_anki_turso.py` :
1. Lit les révisions faites sur l'iPhone depuis `review_log` dans Turso
2. Applique les résultats dans la base SQLite d'Anki Desktop (SM-2)
3. Pousse les cartes dues vers Turso

À lancer manuellement ou via cron sur Mac.

# AnimeCey

Plateforme de streaming d'animés avec bot Telegram intégré.

## Architecture

```
AnimeCey/
├── animecey-backend/     # FastAPI + Pyrogram
│   ├── main.py           # Entrypoint (API + Bot)
│   ├── config.py         # Settings (.env)
│   ├── database.py       # SQLAlchemy async
│   ├── models.py         # ORM models
│   ├── schemas.py        # Pydantic schemas
│   ├── auth.py           # JWT authentication
│   ├── create_admin.py   # CLI admin creation
│   ├── routers/          # API endpoints
│   ├── services/         # External integrations
│   └── bot/              # Telegram bot handlers
├── animecey-frontend/    # React + TypeScript + Vite
│   ├── src/
│   │   ├── api/          # API client layer
│   │   ├── stores/       # Zustand stores
│   │   ├── components/   # UI components
│   │   └── pages/        # Route pages
│   └── public/
│       └── sw.js         # Push notification worker
└── README.md
```

## Backend Setup

```bash
cd animecey-backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python create_admin.py admin admin@example.com your_password
python main.py
```

**API**: http://localhost:8000  
**Docs**: http://localhost:8000/docs

## Frontend Setup

```bash
cd animecey-frontend
npm install
cp .env.example .env
npm run dev
```

**App**: http://localhost:5173

## Features

- **Catalogue** — Animés avec filtres (genre, type, langue, statut, année)
- **Streaming** — Deux serveurs (ServCey 1 via Telegram, ServCey 2 via Byse.sx)
- **Auth** — Inscription, connexion, JWT
- **Utilisateur** — Watchlist, favoris, historique, continuer à regarder
- **Commentaires** — Avec likes et réponses
- **Notifications** — Web Push + broadcasts admin
- **Admin** — Dashboard, gestion des animés/épisodes/users/dossiers
- **Bot Telegram** — Upload d'épisodes via commandes

## Stack

| Backend | Frontend |
|---------|----------|
| FastAPI | React 18 + TypeScript |
| SQLAlchemy 2.0 | Zustand |
| Pyrogram | TanStack React Query |
| SQLite (aiosqlite) | Vite + SWC |
| pywebpush | Tailwind CSS + shadcn/ui |

## API Endpoints

### Public
- `POST /api/auth/register` — Inscription
- `POST /api/auth/login` — Connexion
- `GET /api/animes` — Liste paginée avec filtres
- `GET /api/animes/featured` — Animés en vedette
- `GET /api/animes/{id}` — Détails d'un animé
- `GET /api/episodes` — Liste des épisodes
- `GET /api/episodes/{id}/stream` — URL de streaming
- `GET /api/comments` — Commentaires paginés
- `GET /api/notifications` — Notifications
- `POST /api/push/subscribe` — Push subscription

### Auth Required
- `GET /api/auth/me` — Profil utilisateur
- `POST /api/users/watchlist` — Ajouter à la watchlist
- `POST /api/users/favorites/{anime_id}` — Ajouter aux favoris
- `POST /api/comments` — Poster un commentaire

### Admin Only
- `GET /api/admin/stats` — Statistiques
- `POST /api/admin/animes` — Créer un animé
- `POST /api/admin/broadcasts` — Envoyer une notification
- `GET /api/tmdb/search` — Recherche TMDB
- `POST /api/anilist/search` — Recherche AniList

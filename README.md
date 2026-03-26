# Sitter

Application modulaire full-stack avec architecture feature-based, Feature Registry et RBAC.

## Stack technique

| Couche              | Technologies                                    |
| ------------------- | ----------------------------------------------- |
| **Frontend**        | React 18, TypeScript, Vite, SCSS, i18next       |
| **Backend**         | FastAPI, Python 3.11, SQLAlchemy async, Alembic |
| **Base de donnees** | PostgreSQL 15                                   |
| **Cache / Queue**   | Redis 7, ARQ (background tasks)                 |
| **Infra**           | Docker Compose, GitHub Actions CI               |

## Services

| Service  | Port | Description             |
| -------- | ---- | ----------------------- |
| `db`     | 5480 | PostgreSQL              |
| `redis`  | 6489 | Redis                   |
| `api`    | 5481 | Backend FastAPI         |
| `worker` | —    | Worker ARQ (jobs async) |
| `app`    | 5482 | Frontend React/Vite     |

## Demarrage rapide

```bash
# 1. Copier la config
cp .env.example .env

# 2. Lancer tous les services
docker compose up -d

# 3. L'API applique automatiquement les migrations et demarre
#    Le frontend est accessible sur http://localhost:5482
```

## Developpement

Le fichier `docker-compose.override.yml` monte les volumes locaux pour le hot-reload (uvicorn + vite). Il est charge automatiquement par Docker Compose en dev.

```bash
# Demarrer en dev (hot-reload actif)
docker compose up -d

# Logs d'un service
docker compose logs -f api

# Creer une migration Alembic
docker compose run --rm api alembic -c alembic/alembic.ini revision --autogenerate -m "description"

# Appliquer les migrations
docker compose run --rm api alembic -c alembic/alembic.ini upgrade head
```

## CI

La CI est definie dans `.github/workflows/ci.yml` et s'execute sur push/PR vers `main`/`master` :

1. **Lint backend** — `ruff check`
2. **Lint frontend** — `tsc --noEmit`
3. **Build & migrations** — build Docker, `alembic upgrade head`, `alembic check`, verification du worker

### Verification locale

```bash
# CI complete (necessite act — https://github.com/nektos/act)
act push

# Lints seuls
act -j lint-backend -j lint-frontend
```

## Architecture

```
├── api/                    # Backend FastAPI
│   ├── src/
│   │   ├── core/           # Features template (core)
│   │   ├── features/       # Features projet
│   │   └── main.py
│   └── alembic/            # Migrations
├── app/                    # Frontend React
│   ├── src/
│   │   ├── core/           # Features template (core)
│   │   └── features/       # Features projet
│   └── package.json
├── docker-compose.yml      # Config Docker (base)
├── docker-compose.override.yml  # Volumes dev (hot-reload)
├── .env.example            # Variables d'environnement
└── CHANGELOG.md            # Historique des versions
```

Les features sont decouvertes automatiquement via le **Feature Registry**. Chaque feature declare un `manifest.py` (backend) et peut etre activee/desactivee dynamiquement depuis l'admin.

## Versioning

CalVer : `YYYY.MM.N` (ex: `2026.02.32`). Le compteur N repart a 1 chaque nouveau mois.

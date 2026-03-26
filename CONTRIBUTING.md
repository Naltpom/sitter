# Contribuer

## Prerequis

- Docker & Docker Compose
- Git
- [act](https://github.com/nektos/act) (CI locale)

## Installation

```bash
cp .env.example .env
docker compose up -d
```

L'application est accessible sur `http://localhost:5482`.

## Workflow

1. Creer une branche depuis `master`
2. Developper avec le hot-reload actif (`docker compose up -d`)
3. Verifier les lints avant de commit :
   ```bash
   act push
   ```
4. Commit et push
5. Creer une Pull Request vers `master`

## Conventions

- **Backend** : Python, lint avec `ruff` (config dans `ruff.toml`)
- **Frontend** : TypeScript strict, lint avec `tsc --noEmit`
- **Styles** : SCSS uniquement, pas de style inline, dark + light theme obligatoires
- **i18n** : aucun texte en dur dans les TSX, tout passe par `t('cle')`
- **Commits** : messages descriptifs, versioning CalVer `YYYY.MM.N`
- **Migrations** : Alembic, toujours verifier avec `alembic check`

## Structure d'une feature

Chaque feature suit la structure decrite dans le README. Backend dans `api/src/core/` ou `api/src/features/`, frontend dans `app/src/core/` ou `app/src/features/`.

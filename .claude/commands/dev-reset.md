Tu dois redemarrer l'environnement de developpement Docker et charger les fixtures.

## Etape 1 — Arreter les containers

```bash
docker compose down -v
```

Supprime les containers ET les volumes (DB propre).

## Etape 2 — Reconstruire et demarrer

```bash
docker compose up -d --build
```

Attend que tous les containers soient up (db healthy, api started, app started).

## Etape 3 — Verifier que l'API est prete

```bash
docker compose logs api --tail=20
```

Verifier que :
- `alembic upgrade head` s'est execute sans erreur
- L'API a demarre (uvicorn running)

Si erreur : afficher les logs complets et corriger.

## Etape 4 — Lancer les fixtures (seed)

```bash
docker compose exec api python -m src.seed
```

Verifie que le seed s'est termine avec succes (message "Seed termine avec succes").

## Etape 5 — Lancer les fixtures de masse

```bash
docker compose exec api python -m src.run_fixtures --scale 10000
```

Genere ~10 000 entrees par feature (users, events, notifications, etc.) pour avoir un jeu de donnees realiste. Verifie que la generation se termine sans erreur.

## Etape 6 — Confirmation

Afficher un resume :
- Status des 3 containers (db, api, app)
- Comptes demo disponibles
- URLs d'acces (http://localhost:5482)

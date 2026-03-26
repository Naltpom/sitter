# Architecture de deploiement

## Schema reseau

```
Internet
    |
Cloudflare (CDN / WAF / DDoS)          ← gere par ADMIN SYS
    |
Firewall Cisco HA                       ← gere par ADMIN SYS
    |
Firewall dedie                          ← gere par ADMIN SYS
    |
┌───────────────────────────────────────────────────────────┐
│  Serveur (SITTER-PROD / SITTER-DEV)                          │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Docker Compose                                     │  │
│  │                                                     │  │
│  │  ┌──────────┐  :80/:443                             │  │
│  │  │  Nginx   │◄──── Internet (seuls ports exposes)   │  │
│  │  │ Gateway  │                                       │  │
│  │  └────┬─────┘                                       │  │
│  │       │                                             │  │
│  │  ┌────┴──────────────────────┐                      │  │
│  │  │           │               │                      │  │
│  │  │ /api/*    │ /api/realtime │  /*                   │  │
│  │  │           │ /stream       │                      │  │
│  │  ▼           ▼               ▼                      │  │
│  │  ┌──────┐  ┌──────┐  ┌──────────┐                  │  │
│  │  │ API  │  │ API  │  │ App      │                  │  │
│  │  │:8000 │  │ SSE  │  │ Nginx    │                  │  │
│  │  └──┬───┘  └──────┘  │ :80     │                  │  │
│  │     │                 │ (dist/) │                  │  │
│  │     │                 └─────────┘                  │  │
│  │  ┌──┴───┐                                          │  │
│  │  │Worker│  (meme image que API)                    │  │
│  │  │ ARQ  │                                          │  │
│  │  └──┬───┘                                          │  │
│  │     │                                              │  │
│  │  ┌──┴──────────────────────────────────┐           │  │
│  │  │                                     │           │  │
│  │  ▼            ▼           ▼            ▼           │  │
│  │  ┌─────────┐ ┌─────┐ ┌───────────┐ ┌──────┐      │  │
│  │  │PgBouncer│ │Redis│ │Meilisearch│ │ClamAV│      │  │
│  │  │ :6432   │ │:6379│ │  :7700    │ │:3310 │      │  │
│  │  └────┬────┘ └─────┘ └───────────┘ └──────┘      │  │
│  │       │                                            │  │
│  │       ▼                                            │  │
│  │  ┌──────────┐                                      │  │
│  │  │PostgreSQL│                                      │  │
│  │  │  :5432   │                                      │  │
│  │  │ pgvector │                                      │  │
│  │  └──────────┘                                      │  │
│  │                                                     │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Volumes Docker:                                          │
│  - postgres_data    (donnees DB)                          │
│  - redis_data       (cache/queue)                         │
│  - upload_files     (fichiers uploades)                   │
│  - rich_text_images (images editeur)                      │
│  - meilisearch_data (index de recherche)                  │
│  - clamav_data      (signatures antivirus)                │
│  - certbot_conf     (certificats SSL)                     │
│  - certbot_www      (ACME challenge)                      │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## Services Docker

| Service         | Image                  | Port interne | Port expose | Role                              |
| --------------- | ---------------------- | ------------ | ----------- | --------------------------------- |
| **nginx**       | nginx:1.27-alpine      | 80, 443      | 80, 443     | Gateway SSL, reverse proxy        |
| **app**         | Multi-stage Bun→Nginx  | 80           | —           | Frontend SPA (fichiers statiques) |
| **api**         | python:3.11-slim       | 8000         | —           | API REST FastAPI                  |
| **worker**      | python:3.11-slim       | —            | —           | Background jobs (ARQ)             |
| **db**          | postgres:15 + pgvector | 5432         | —           | Base de donnees                   |
| **pgbouncer**   | edoburu/pgbouncer      | 6432         | —           | Connection pooling                |
| **redis**       | redis:7-alpine         | 6379         | —           | Cache, queue, rate limiting       |
| **meilisearch** | meilisearch:v1.12      | 7700         | —           | Recherche full-text               |
| **clamav**      | clamav/clamav:stable   | 3310         | —           | Scan antivirus uploads            |
| **certbot**     | certbot/certbot        | —            | —           | Renouvellement SSL auto           |

## Flux de donnees

### Requete utilisateur standard

```
Navigateur → Cloudflare → Nginx → App (HTML/CSS/JS statique)
Navigateur → Cloudflare → Nginx → API → PgBouncer → PostgreSQL
```

### Realtime (SSE)

```
Navigateur → Cloudflare → Nginx (proxy_buffering off) → API SSE → queue asyncio
```

### Background jobs

```
API → Redis (enqueue) → Worker ARQ → PgBouncer → PostgreSQL
                                   → SMTP (emails)
                                   → Meilisearch (indexation)
                                   → Webhooks (HTTP externe)
```

### Upload de fichier

```
Navigateur → Nginx (max 50MB) → API → ClamAV (scan) → Volume Docker (uploads/)
```

## Environnements

| Environnement  | Serveur VPS | Specs                  | Usage                   |
| -------------- | ----------- | ---------------------- | ----------------------- |
| **Production** | SITTER-PROD | 8 cores, 16 Go, 2 To   | Utilisateurs finaux     |
| **Staging**    | SITTER-DEV  | 4 cores, 8 Go, 146 Go  | Tests pre-production    |
| **Recette**    | SITTER-DEV  | (partage avec staging) | Validation client       |
| **PRA**        | SITTER-PRA  | 8 cores, 16 Go, 146 Go | Reprise d'activite (1h) |
| **Dev**        | Local       | Variable               | Developpement           |

Tous les environnements sauf "Dev" utilisent `docker-compose.prod.yml`.
La difference entre staging, recette et production = le fichier `.env`.

## Multi-clients

Chaque client = 1 clone du template = 1 stack Docker independant.

```
Serveur client A                    Serveur client B
┌──────────────────┐               ┌──────────────────┐
│ /app/             │               │ /app/             │
│ .env (domaine A) │               │ .env (domaine B) │
│ secrets/          │               │ secrets/          │
│ Docker Compose    │               │ Docker Compose    │
│ DB: client_a_db   │               │ DB: client_b_db   │
│ Branding: logo A  │               │ Branding: logo B  │
│ Features: X, Y    │               │ Features: X, Z    │
└──────────────────┘               └──────────────────┘
```

- Isolation totale des donnees (RGPD)
- Personnalisation via admin UI (logo, couleurs, nom)
- Features independantes via feature_flags
- Pas de refactoring multi-tenant necessaire

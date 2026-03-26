# Sauvegardes et restauration

## Strategie de backup

| Quoi             | Comment               | Frequence                | Retention |
| ---------------- | --------------------- | ------------------------ | --------- |
| Base de donnees  | `pg_dump` compresse   | Quotidien (cron)         | 30 jours  |
| Fichiers uploads | tar.gz des volumes    | Quotidien (cron)         | 30 jours  |
| Meilisearch      | Snapshot interne      | Auto (rebuild possible)  | —         |
| Secrets          | Fichiers `./secrets/` | Copie manuelle securisee | —         |

> **Note infra Syspark** : les backups horaires et le PRA (sync quotidienne + activation 1h)
> sont geres au niveau infrastructure. Les backups applicatifs ci-dessous sont un filet
> de securite supplementaire.

---

## Backup automatique (cron)

### Mise en place

```bash
# Rendre le script executable
chmod +x deploy/scripts/backup.sh

# Ajouter au cron (backup quotidien a 3h du matin)
(crontab -l 2>/dev/null; echo "0 3 * * * cd /app && ./deploy/scripts/backup.sh >> /var/log/sitter-backup.log 2>&1") | crontab -
```

### Execution manuelle

```bash
cd /app
./deploy/scripts/backup.sh
```

Les fichiers sont crees dans `./backups/` :

- `db_YYYYMMDD_HHMMSS.dump` — dump PostgreSQL (format custom, compresse)
- `uploads_YYYYMMDD_HHMMSS.tar.gz` — fichiers uploades

### Configuration

Variables d'environnement (dans le shell ou en prefixe de la commande) :

- `BACKUP_DIR` : dossier de destination (defaut: `./backups`)
- `RETENTION_DAYS` : nombre de jours de retention (defaut: 30)

```bash
BACKUP_DIR=/mnt/backup RETENTION_DAYS=90 ./deploy/scripts/backup.sh
```

---

## Restauration

### Restaurer la base de donnees

```bash
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

# 1. Identifier le backup a restaurer
ls -la backups/db_*.dump

# 2. Stopper l'API et le worker (eviter les ecritures pendant la restauration)
$COMPOSE stop api worker

# 3. Restaurer (remplace le contenu de la DB)
cat backups/db_20260302_030000.dump | \
  $COMPOSE exec -T db pg_restore -U $POSTGRES_USER -d $POSTGRES_DB --clean --if-exists

# 4. Redemarrer
$COMPOSE start api worker
```

### Restaurer les fichiers uploads

```bash
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

# 1. Copier l'archive dans le container API
docker cp backups/uploads_20260302_030000.tar.gz sitter_api:/tmp/

# 2. Extraire
$COMPOSE exec api tar xzf /tmp/uploads_20260302_030000.tar.gz -C /

# 3. Nettoyer
$COMPOSE exec api rm /tmp/uploads_20260302_030000.tar.gz
```

### Restaurer les secrets

Les secrets ne sont pas sauvegardes automatiquement (securite).
Conserver une copie securisee hors-serveur (coffre-fort, gestionnaire de secrets).

```bash
# Copier depuis un backup securise
scp backup-server:/safe/secrets/* ./secrets/
chmod 600 secrets/*
```

---

## Verification des backups

Tester regulierement la restauration sur l'environnement de staging :

```bash
# Sur le serveur staging
scp prod-server:/app/backups/db_latest.dump /app/backups/
cat /app/backups/db_latest.dump | \
  docker compose exec -T db pg_restore -U $POSTGRES_USER -d $POSTGRES_DB --clean --if-exists
```

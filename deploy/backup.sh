#!/usr/bin/env bash
# Ежедневный бэкап prod-БД (cron — ставит deploy/server-setup.sh):
# pg_dump → gzip → /var/backups/smeta (хранение 30 дней) + копия в MinIO
# prod-стека (bucket "backups"). Восстановление — docs/runbook.md.
set -euo pipefail
cd "$(dirname "$0")/.."

STAMP=$(date +%Y%m%d-%H%M%S)
DUMP="/var/backups/smeta/daily-${STAMP}.sql.gz"
mkdir -p /var/backups/smeta

docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$DUMP"
echo "Дамп: $DUMP ($(du -h "$DUMP" | cut -f1))"

# Копия в MinIO prod-стека (best-effort: бэкап на диске уже есть)
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T minio \
  sh -c 'mc alias set local http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null \
         && mc mb -p local/backups >/dev/null 2>&1 || true' || true
docker compose -f docker-compose.prod.yml --env-file .env.prod cp "$DUMP" minio:/tmp/bkp.sql.gz \
  && docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T minio \
     sh -c "mc cp /tmp/bkp.sql.gz local/backups/daily-${STAMP}.sql.gz >/dev/null && rm /tmp/bkp.sql.gz" \
  && echo "Копия в MinIO: backups/daily-${STAMP}.sql.gz" \
  || echo "ПРЕДУПРЕЖДЕНИЕ: копия в MinIO не удалась (дамп на диске сохранён)"

# Ротация: локально и в MinIO храним 30 дней
find /var/backups/smeta -name '*.sql.gz' -mtime +30 -delete
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T minio \
  sh -c 'mc rm --recursive --force --older-than 30d local/backups/ >/dev/null 2>&1' || true

echo "Актуальных бэкапов: $(ls /var/backups/smeta/*.sql.gz 2>/dev/null | wc -l)"

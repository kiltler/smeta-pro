#!/usr/bin/env bash
# Промоут на PROD: ТОТ ЖЕ образ, что проверен на staging (без пересборки).
# Перед миграцией — автоматический pg_dump prod-БД.
# Запуск: ./deploy/promote.sh   (после ручного чек-листа staging — docs/runbook.md)
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=$(cat .staging-image 2>/dev/null) || {
  echo "Нет .staging-image — сначала ./deploy/deploy.sh"; exit 1;
}
echo "== Промоут ${IMAGE} на prod =="

echo "== Автодамп prod-БД перед миграцией =="
mkdir -p /var/backups/smeta
DUMP="/var/backups/smeta/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz"
if docker compose -f docker-compose.prod.yml --env-file .env.prod ps db --format '{{.Status}}' 2>/dev/null | grep -q Up; then
  docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db \
    sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$DUMP"
  echo "Дамп: $DUMP ($(du -h "$DUMP" | cut -f1))"
else
  echo "Prod-БД ещё не запущена (первый деплой) — дамп пропущен"
fi

echo "== История образов (для rollback, храним минимум 3) =="
touch .prod-image-history
CURRENT=$(tail -1 .prod-image-history 2>/dev/null || true)
if [ "$CURRENT" != "$IMAGE" ]; then
  echo "$IMAGE" >> .prod-image-history
fi

echo "== Prod up =="
IMAGE="$IMAGE" docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

echo "== Health-check =="
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8201/health > /dev/null; then
    docker tag "$IMAGE" smeta-pro:prod-current  # для ад-хок команд без IMAGE
    echo "OK: prod на ${IMAGE} ($(curl -s http://127.0.0.1:8201/health))"
    # чистим старые образы, всегда оставляя 3 последних из истории
    tail -3 .prod-image-history > /tmp/keep-images
    docker images 'smeta-pro' --format '{{.Repository}}:{{.Tag}}' \
      | grep -vxF -f /tmp/keep-images \
      | grep -vE ":(staging|prod-current)$" \
      | xargs -r docker rmi 2>/dev/null || true
    exit 0
  fi
  sleep 2
done
echo "FAIL: prod не поднялся — откатывайтесь: ./deploy/rollback.sh"
docker compose -f docker-compose.prod.yml --env-file .env.prod logs --tail 50 api
exit 1

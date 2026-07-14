#!/usr/bin/env bash
# Откат PROD на предыдущий образ одной командой (< 5 минут).
# Схема БД не откатывается: миграции аддитивные, старый код работает
# с новой схемой (CLAUDE.md 7.4). Восстановление данных из дампа —
# отдельная процедура в docs/runbook.md.
set -euo pipefail
cd "$(dirname "$0")/.."

PREV=$(tail -2 .prod-image-history 2>/dev/null | head -1)
CURRENT=$(tail -1 .prod-image-history 2>/dev/null)
if [ -z "$PREV" ] || [ "$PREV" = "$CURRENT" ]; then
  echo "Нет предыдущего образа в .prod-image-history — откатывать не на что"; exit 1;
fi

echo "== Откат prod: ${CURRENT} → ${PREV} =="
IMAGE="$PREV" docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8201/health > /dev/null; then
    docker tag "$PREV" smeta-pro:prod-current
    # фиксируем откат в истории (текущим становится PREV)
    sed -i '$d' .prod-image-history
    echo "OK: prod откатился на ${PREV}"
    exit 0
  fi
  sleep 2
done
echo "FAIL: откат не поднялся, логи:"
docker compose -f docker-compose.prod.yml --env-file .env.prod logs --tail 50 api
exit 1

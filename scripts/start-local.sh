#!/usr/bin/env bash
# Локальный стенд одной командой: стек + миграции + демо-пользователь.
# Запуск из корня репозитория:  ./scripts/start-local.sh
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { cp .env.example .env; echo "Создан .env из .env.example"; }

echo "== Поднимаю стек (первый раз — несколько минут) =="
docker compose up -d --build

echo -n "== Жду API "
for i in $(seq 1 90); do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then echo " ✓"; break; fi
  echo -n "."; sleep 2
  [ "$i" = 90 ] && { echo " FAIL"; docker compose logs api | tail -30; exit 1; }
done

echo "== Демо-пользователь и прайс =="
docker compose exec -T api python scripts/seed_demo.py

echo -n "== Жду фронтенд "
for i in $(seq 1 90); do
  if curl -sf http://localhost:5173 > /dev/null 2>&1; then echo " ✓"; break; fi
  echo -n "."; sleep 2
  [ "$i" = 90 ] && { echo " FAIL"; docker compose logs frontend | tail -20; exit 1; }
done

# IP компьютера в локальной сети (для телефона)
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "${IP:-}" ] && IP=$(ipconfig getifaddr en0 2>/dev/null || true)   # macOS
[ -z "${IP:-}" ] && IP=localhost
DEV_CODE=$(grep -E '^AUTH_DEV_CODE=' .env | cut -d= -f2)

cat <<INFO

┌────────────────────────────────────────────────────────────┐
  СметаПро запущена!

  Приложение (комп):     http://localhost:5173
  Приложение (телефон):  http://${IP}:5173
     ↑ открывайте по этому адресу и на компе, если будете
       отправлять клиентские ссылки на телефон

  Вход: телефон  +7 999 000-00-00
        код      ${DEV_CODE:-смотрите в логах: docker compose logs api | grep SMS}

  Админка:        http://${IP}:8000/admin  (логин/пароль из .env)
  MinIO-консоль:  http://${IP}:9001  (minioadmin / minioadmin)

  Сброс к чистому состоянию:  ./scripts/reset-local.sh
└────────────────────────────────────────────────────────────┘
INFO

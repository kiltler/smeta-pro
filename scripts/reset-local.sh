#!/usr/bin/env bash
# Полный сброс локального стенда: удаляет БД и файлы, поднимает заново
# с чистым демо-пользователем.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Останавливаю стек и удаляю данные (БД, MinIO) =="
docker compose down -v

exec ./scripts/start-local.sh

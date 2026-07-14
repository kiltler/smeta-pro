#!/usr/bin/env bash
# Деплой на STAGING: собрать образ с тегом по git-хэшу → поднять staging-стек.
# Запускается на сервере из /opt/smeta-pro (или вызывается GitHub Actions).
set -euo pipefail
cd "$(dirname "$0")/.."

GIT_SHA=$(git rev-parse --short HEAD)
IMAGE="smeta-pro:${GIT_SHA}"
echo "== Сборка ${IMAGE} =="

echo "-- фронтенд --"
(cd frontend && npm ci --no-audit --no-fund && npm run build)

echo "-- образ --"
docker build -f deploy/Dockerfile.release -t "$IMAGE" .

echo "== Staging up =="
IMAGE="$IMAGE" docker compose -f docker-compose.staging.yml --env-file .env.staging up -d

echo "== Health-check =="
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8101/health > /dev/null; then
    docker tag "$IMAGE" smeta-pro:staging  # для ад-хок команд без IMAGE
    echo "$IMAGE" > .staging-image
    echo "OK: staging на ${IMAGE} ($(curl -s http://127.0.0.1:8101/health))"
    exit 0
  fi
  sleep 2
done
echo "FAIL: staging не поднялся, логи:"
docker compose -f docker-compose.staging.yml --env-file .env.staging logs --tail 50 api
exit 1

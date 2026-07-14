#!/usr/bin/env bash
# Первичная настройка VPS (Ubuntu 24.04). Запускается ОДИН раз под root:
#   APP_DOMAIN=app.example.ru STAGING_DOMAIN=staging.example.ru \
#   STAGING_AUTH_USER=smeta STAGING_AUTH_PASSWORD='...' ./deploy/server-setup.sh
set -euo pipefail

: "${APP_DOMAIN:?пример: APP_DOMAIN=app.example.ru}"
: "${STAGING_DOMAIN:?пример: STAGING_DOMAIN=staging.example.ru}"
: "${STAGING_AUTH_USER:?логин basic auth для staging}"
: "${STAGING_AUTH_PASSWORD:?пароль basic auth для staging}"

echo "== Пакеты: docker, nginx, certbot, node =="
apt-get update
apt-get install -y ca-certificates curl gnupg nginx certbot python3-certbot-nginx apache2-utils
# Docker (официальный репозиторий)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
# Node 22 (сборка фронтенда при деплое)
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs

echo "== Каталоги =="
mkdir -p /opt/smeta-pro /var/backups/smeta

echo "== Basic auth для staging =="
htpasswd -bc /etc/nginx/.htpasswd_smeta "$STAGING_AUTH_USER" "$STAGING_AUTH_PASSWORD"

echo "== nginx-конфиг из шаблона =="
export APP_DOMAIN STAGING_DOMAIN
envsubst '${APP_DOMAIN} ${STAGING_DOMAIN}' \
  < /opt/smeta-pro/deploy/nginx/smeta.conf.template \
  > /etc/nginx/sites-available/smeta.conf
ln -sf /etc/nginx/sites-available/smeta.conf /etc/nginx/sites-enabled/smeta.conf
rm -f /etc/nginx/sites-enabled/default

echo "== Сертификаты Let's Encrypt =="
# certbot сам поправит конфиг и настроит автообновление (systemd timer)
certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email \
  -d "$APP_DOMAIN" -d "$STAGING_DOMAIN" || {
  echo "!! certbot не смог выпустить сертификаты — проверьте, что DNS A-записи"
  echo "!! $APP_DOMAIN и $STAGING_DOMAIN указывают на IP этого сервера."
  exit 1
}
nginx -t && systemctl reload nginx

echo "== Ежедневный бэкап prod-БД (03:30) =="
cat > /etc/cron.d/smeta-backup <<CRON
30 3 * * * root /opt/smeta-pro/deploy/backup.sh >> /var/log/smeta-backup.log 2>&1
CRON

echo
echo "Готово. Дальше:"
echo "1) git clone репозитория в /opt/smeta-pro (если ещё не)"
echo "2) создать /opt/smeta-pro/.env.staging и .env.prod из deploy/env.*.example"
echo "3) ./deploy/deploy.sh — первый деплой staging"

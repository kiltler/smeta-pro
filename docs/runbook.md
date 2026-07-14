# Runbook — эксплуатация «СметаПро»

## Локальное тестирование

Полный стенд на своей машине: `./scripts/start-local.sh` — поднимает стек,
сидит демо-пользователя (`+7 999 000-00-00`, код `0000`), печатает адреса,
включая `http://<IP-компа>:5173` для телефона в той же Wi-Fi-сети.
Сброс данных к чистому состоянию: `./scripts/reset-local.sh`.
Мок-режимы локального стенда: `MOCK_BILLING=true` (Pro без ЮKassa),
`PARSE_ENABLED=mock` (парсер без LLM), `AUTH_DEV_CODE=0000` (вход без SMS).
**Эти переменные никогда не задаются на staging/prod.** Подробнее — README.

Один VPS (Ubuntu 24.04), два изолированных стека docker compose:
staging (порт 127.0.0.1:8101) и prod (127.0.0.1:8201). Снаружи — nginx
с HTTPS: `https://staging.<домен>` (за basic auth) и `https://app.<домен>`.
Репозиторий на сервере: `/opt/smeta-pro`. Бэкапы: `/var/backups/smeta`.

## Подключение к серверу

```bash
ssh root@<IP-сервера>          # или пользователь с sudo и группой docker
cd /opt/smeta-pro
```

## Первичная настройка сервера (один раз)

```bash
git clone <репозиторий> /opt/smeta-pro && cd /opt/smeta-pro
cp deploy/env.staging.example .env.staging   # заполнить секреты!
cp deploy/env.prod.example   .env.prod       # секреты ДРУГИЕ, не копия staging
APP_DOMAIN=app.<домен> STAGING_DOMAIN=staging.<домен> \
STAGING_AUTH_USER=smeta STAGING_AUTH_PASSWORD='<пароль>' \
  ./deploy/server-setup.sh
./deploy/deploy.sh                            # первый деплой staging
./deploy/promote.sh                           # первый деплой prod
```

GitHub Actions: в настройках репозитория → Secrets добавить
`STAGING_SSH_HOST`, `STAGING_SSH_USER`, `STAGING_SSH_KEY` (приватный ключ).

## Штатный релиз

1. PR → тесты зелёные → merge в `main`.
2. GitHub Actions сам задеплоит main на staging (`deploy/deploy.sh`).
3. Пройти чек-лист staging (ниже). Всё ок →
4. ```bash
   ssh root@<IP> 'cd /opt/smeta-pro && ./deploy/promote.sh'
   git tag release-X.Y.Z && git push --tags   # пометить релиз
   ```
   `promote.sh` ставит на prod **тот же образ**, что тестировался на staging
   (тег = git-хэш), перед миграцией автоматически снимает дамп prod-БД.

## Чек-лист проверки staging перед релизом (8 пунктов, CLAUDE.md 7.3)

Открыть `https://staging.<домен>` (basic auth), дальше по порядку:

1. **Регистрация нового юзера** — ввести новый номер; код смотреть:
   `docker compose -f docker-compose.staging.yml --env-file .env.staging logs api | grep SMS | tail -1`
2. **Создание сметы через парсер** — таб «Текст»: «монтаж девятки, трасса
   4 метра» → позиции распознаны. *Пока PARSE_ENABLED=false — вместо этого
   собрать смету из шаблонов (комплект + степперы).*
3. **PDF открывается** — «Документы» → PDF: файл скачивается, логотип/бренд/
   итог на месте (на Free — водяной знак внизу).
4. **Публичная ссылка работает** — «Ссылка клиенту» → открыть в приватном
   окне (без basic auth не откроется — ссылку проверять в том же браузере,
   либо curl -u): смета видна, статус у мастера стал «Просмотрена».
5. **Договор + акт генерируются** — согласовать смету по ссылке, на смете
   «Договор + акт», заполнить форму → оба PDF открываются, НПД-фраза в договоре.
6. **Тестовый платёж ЮKassa проходит** — Профиль → «Подключить Pro» →
   страница ЮKassa → тестовая карта `5555 5555 5555 4477`, 12/29, CVC 123.
7. **Вебхук обработан** — после оплаты обновить Профиль: тариф Pro, дата
   списания через 30 дней. Если нет — проверить, что в кабинете тестового
   магазина ЮKassa настроен вебхук `https://staging.<домен>/billing/webhook`.
8. **Лимит Free срабатывает** — новым (Free) юзером создать 3 сметы,
   4-я должна показать пейволл «Создано 3 документа в этом месяце».

## Откат prod (цель: 5 минут одной командой)

```bash
ssh root@<IP> 'cd /opt/smeta-pro && ./deploy/rollback.sh'
```

Откатывает на предыдущий образ из `.prod-image-history` (последние 3 образа
хранятся всегда). Схема БД не откатывается — миграции аддитивные, старый код
работает с новой схемой. Если данные повреждены — восстановление из дампа ниже.

## Восстановление БД из бэкапа

Бэкапы: ежедневно 03:30 (cron `/etc/cron.d/smeta-backup`) в
`/var/backups/smeta/daily-*.sql.gz` (30 дней) + копия в MinIO prod (`backups/`);
перед каждым promote — `pre-deploy-*.sql.gz`.

```bash
cd /opt/smeta-pro
ls -lt /var/backups/smeta | head            # выбрать дамп
docker compose -f docker-compose.prod.yml --env-file .env.prod stop api
gunzip -c /var/backups/smeta/<дамп>.sql.gz | \
  docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db \
  sh -c 'dropdb -U "$POSTGRES_USER" --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB" && psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose -f docker-compose.prod.yml --env-file .env.prod start api
curl -s https://app.<домен>/api/health      # {"status":"ok",...}
```

Ежемесячная проверка бэкапов: тот же restore на **staging**-стек
(`-f docker-compose.staging.yml --env-file .env.staging`) из свежего дампа prod.

## Диагностика

```bash
# логи
docker compose -f docker-compose.staging.yml --env-file .env.staging logs -f api
docker compose -f docker-compose.prod.yml   --env-file .env.prod   logs -f api
# здоровье (изнутри сервера)
curl -s http://127.0.0.1:8101/health   # staging
curl -s http://127.0.0.1:8201/health   # prod
# nginx
nginx -t && systemctl reload nginx
journalctl -u nginx --since "1 hour ago"
# сертификаты (автообновление — systemd-таймер certbot)
certbot renew --dry-run
# место на диске / старые образы (последние 3 prod-образа не трогать!)
df -h; docker system df
```

## Что где лежит

| Что | Где |
|---|---|
| Код | `/opt/smeta-pro` (ветка main) |
| Секреты | `/opt/smeta-pro/.env.staging`, `.env.prod` (в git не попадают) |
| Текущий staging-образ | `.staging-image` |
| История prod-образов | `.prod-image-history` (последние 3 хранятся) |
| Бэкапы БД | `/var/backups/smeta` + MinIO prod bucket `backups` |
| nginx | `/etc/nginx/sites-available/smeta.conf`, basic auth `/etc/nginx/.htpasswd_smeta` |
| Cron бэкапа | `/etc/cron.d/smeta-backup` (03:30 ежедневно) |

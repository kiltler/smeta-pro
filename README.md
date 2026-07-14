# СметаПро

SaaS для частных мастеров: смета голосом/текстом/шаблонами за минуты, PDF
с брендом мастера, публичная ссылка для согласования, договор и акт одной кнопкой.

Правила проекта — в [CLAUDE.md](CLAUDE.md).

## Стек

FastAPI · PostgreSQL 16 · MinIO (S3) · SQLAlchemy 2 + Alembic · Docker Compose

## Локальное тестирование (одна команда)

```bash
./scripts/start-local.sh
```

Скрипт поднимает весь стек, накатывает миграции, создаёт демо-пользователя
с прайсом «кондиционерщик» и печатает все адреса и данные для входа:

- **Приложение: http://localhost:5173**, вход — телефон `+7 999 000-00-00`,
  код `0000` (универсальный dev-код `AUTH_DEV_CODE` из `.env`; работает
  для любого номера — можно регистрировать сколько угодно тестовых юзеров)
- Админка: http://localhost:8000/admin (`ADMIN_USER`/`ADMIN_PASSWORD` из `.env`)
- MinIO-консоль: http://localhost:9001 (minioadmin/minioadmin)
- Swagger: http://localhost:8000/docs

**С телефона в той же Wi-Fi-сети:** скрипт печатает адрес вида
`http://<IP-компа>:5173` — открывайте его. Если планируете отправлять
клиентские ссылки смет на телефон, открывайте приложение по этому адресу
и на компьютере: публичные ссылки строятся от хоста в адресной строке.

**Мок-режимы** (включены в `.env.example`, на серверы не переносятся):
- `MOCK_BILLING=true` — «Подключить Pro» активирует подписку мгновенно,
  без ЮKassa: удобно тестировать пейволл, лимит, водяной знак, отмену;
- `PARSE_ENABLED=mock` — табы «Голос»/«Текст» работают без LLM:
  детерминированный разбор по синонимам прайса (`true` — реальный
  Anthropic API, `false` — только «Шаблоны»).

**Сброс к чистому состоянию** (удаляет БД и файлы, поднимает заново):

```bash
./scripts/reset-local.sh
```

## Частые команды

```bash
docker compose up -d          # поднять в фоне
docker compose logs -f api    # логи API
docker compose down           # остановить
docker compose down -v        # остановить и удалить данные (БД и файлы!)
```

## Миграции (Alembic)

```bash
# создать миграцию по изменениям моделей
docker compose exec api alembic revision --autogenerate -m "описание"

# применить миграции
docker compose exec api alembic upgrade head

# откатить последнюю
docker compose exec api alembic downgrade -1
```

## Сид прайса «кондиционерщик»

```bash
# заполняет прайс (13 позиций) и комплекты (5) для пользователя с указанным id;
# повторный запуск данные не дублирует
docker compose exec api python scripts/seed_hvac.py <user_id>
```

## Тесты

```bash
docker compose exec api pytest
```

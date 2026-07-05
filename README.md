# СметаПро

SaaS для частных мастеров: смета голосом/текстом/шаблонами за минуты, PDF
с брендом мастера, публичная ссылка для согласования, договор и акт одной кнопкой.

Правила проекта — в [CLAUDE.md](CLAUDE.md).

## Стек

FastAPI · PostgreSQL 16 · MinIO (S3) · SQLAlchemy 2 + Alembic · Docker Compose

## Быстрый старт

```bash
# 1. Переменные окружения (значения по умолчанию подходят для локальной разработки)
cp .env.example .env

# 2. Поднять всё: API + Postgres + MinIO
docker compose up --build

# 3. Проверить здоровье сервиса (БД + хранилище)
curl http://localhost:8000/health
# → {"status":"ok","db":"ok","storage":"ok"}
```

- API: http://localhost:8000 (Swagger — http://localhost:8000/docs)
- Веб-консоль MinIO: http://localhost:9001 (логин/пароль — `S3_ACCESS_KEY`/`S3_SECRET_KEY` из `.env`)

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

## Тесты

```bash
docker compose exec api pytest
```

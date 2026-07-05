"""Общие фикстуры: каждый тест получает свежую временную БД,
чтобы не трогать данные разработки."""
import uuid

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.config import settings


def alembic_config(db_url: str) -> Config:
    """Конфиг Alembic, направленный на указанную БД."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture(scope="session")
def pg_admin_engine():
    """Соединение с сервером Postgres для создания/удаления временных БД."""
    admin_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    yield engine
    engine.dispose()


@pytest.fixture
def temp_db_url(pg_admin_engine):
    """Свежая пустая БД на время одного теста."""
    name = f"smeta_test_{uuid.uuid4().hex[:8]}"
    with pg_admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    yield settings.database_url.rsplit("/", 1)[0] + f"/{name}"
    with pg_admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))

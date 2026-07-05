"""Общие фикстуры: каждый тест получает свежую временную БД,
чтобы не трогать данные разработки."""
import uuid

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import get_db
from app.main import app


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


@pytest.fixture
def test_engine(temp_db_url):
    """Временная БД с накатанными миграциями."""
    command.upgrade(alembic_config(temp_db_url), "head")
    engine = create_engine(temp_db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Сессия для подготовки/проверки данных прямо из теста."""
    TestSession = sessionmaker(bind=test_engine)
    with TestSession() as session:
        yield session


@pytest.fixture
def client(test_engine):
    """HTTP-клиент приложения, подключённого к временной БД."""
    TestSession = sessionmaker(bind=test_engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()

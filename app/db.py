"""Подключение к PostgreSQL: engine и фабрика сессий."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI-зависимость: сессия БД на время запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db() -> None:
    """Проверка соединения с БД (используется в /health). Бросает исключение при недоступности."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

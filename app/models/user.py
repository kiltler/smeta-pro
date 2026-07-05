"""Пользователь и его профиль (бренд, реквизиты для документов)."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    role: Mapped[str] = mapped_column(String(20), server_default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    brand_name: Mapped[str | None] = mapped_column(String(200))
    full_name: Mapped[str | None] = mapped_column(String(200))
    inn: Mapped[str | None] = mapped_column(String(12))
    # Реквизиты (банк, счёт и т.п.) — гибкий jsonb, состав полей уточнится в задаче 3
    requisites: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    # Ключи файлов в хранилище (см. app/storage.py)
    logo_key: Mapped[str | None] = mapped_column(String(500))
    signature_key: Mapped[str | None] = mapped_column(String(500))

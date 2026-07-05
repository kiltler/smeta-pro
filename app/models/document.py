"""Документы (смета/договор/акт) и логи ИИ-парсинга."""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("type IN ('estimate', 'contract', 'act')", name="type_valid"),
        CheckConstraint("status IN ('draft', 'sent', 'approved')", name="status_valid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    # Снапшот позиций и сумм: изменение прайса задним числом не меняет документ
    payload: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    pdf_key: Mapped[str | None] = mapped_column(String(500))
    # Неугадываемый идентификатор публичной ссылки; появляется при отправке клиенту
    public_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # У договора/акта — ссылка на родительскую смету
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ParseLog(Base):
    __tablename__ = "parse_logs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    raw_input: Mapped[str] = mapped_column(Text)
    parsed_json: Mapped[dict] = mapped_column(JSONB)
    # Что пользователь поправил руками — материал для улучшения промпта
    corrected_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

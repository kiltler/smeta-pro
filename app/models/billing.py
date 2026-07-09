"""Биллинг: подписки, счётчики лимита Free, идемпотентность вебхуков.

ВНИМАНИЕ (CLAUDE.md 9.6): схему биллинга не менять без явной команды владельца.
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("plan IN ('free', 'pro', 'business')", name="plan_valid"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    plan: Mapped[str] = mapped_column(String(20), server_default="free")
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    yookassa_payment_method_id: Mapped[str | None] = mapped_column(String(100))


class BillingEvent(Base):
    """Обработанные события биллинга: повторная доставка вебхука или повторная
    попытка автосписания находят свой ключ здесь и не выполняются дважды."""

    __tablename__ = "billing_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    event_key: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UsageCounter(Base):
    __tablename__ = "usage_counters"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Месяц в формате "ГГГГ-ММ", например "2026-07"
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    documents_created: Mapped[int] = mapped_column(Integer, server_default="0")

"""Биллинг: подписки и счётчики лимита Free.

ВНИМАНИЕ (CLAUDE.md 9.6): схему биллинга не менять без явной команды владельца.
"""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String
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


class UsageCounter(Base):
    __tablename__ = "usage_counters"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Месяц в формате "ГГГГ-ММ", например "2026-07"
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    documents_created: Mapped[int] = mapped_column(Integer, server_default="0")

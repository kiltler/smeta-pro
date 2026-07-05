"""Прайс-лист пользователя: позиции и комплекты (bundles)."""
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Identity, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PriceItem(Base):
    __tablename__ = "price_items"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Ниша справочника: hvac / plumbing / electric (мультиниша — в данных, не в коде)
    niche: Mapped[str] = mapped_column(String(20), server_default="hvac")
    name: Mapped[str] = mapped_column(String(200))
    # Синонимы для матчинга ИИ-парсером («девятка» → «Монтаж сплит-системы 09»)
    synonyms: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    unit: Mapped[str] = mapped_column(String(20))  # шт / м / компл / услуга
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    sort: Mapped[int] = mapped_column(Integer, server_default="0")


class Bundle(Base):
    __tablename__ = "bundles"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    sort: Mapped[int] = mapped_column(Integer, server_default="0")
    # Массив объектов {price_item_id, qty_default, ask_qty(bool)}
    items: Mapped[list] = mapped_column(JSONB, server_default="[]")

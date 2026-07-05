"""Сид «кондиционерщик»: создаёт прайс и комплекты, не дублирует при повторе."""
from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Bundle, PriceItem, User
from scripts.seed_hvac import BUNDLES, PRICE_ITEMS, seed_hvac
from tests.conftest import alembic_config


@pytest.fixture
def session(temp_db_url):
    command.upgrade(alembic_config(temp_db_url), "head")
    engine = create_engine(temp_db_url)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def user(session):
    user = User(phone="+79990000001")
    session.add(user)
    session.commit()
    return user


def test_seed_creates_items_and_bundles(session, user):
    items_count, bundles_count = seed_hvac(session, user.id)
    session.commit()

    items = session.scalars(select(PriceItem).where(PriceItem.user_id == user.id)).all()
    bundles = session.scalars(select(Bundle).where(Bundle.user_id == user.id)).all()

    assert items_count == len(items) == len(PRICE_ITEMS) == 13
    assert bundles_count == len(bundles) == len(BUNDLES) == 5
    assert all(item.niche == "hvac" for item in items)

    # Цены из задания на месте
    by_name = {item.name: item for item in items}
    assert by_name["Монтаж сплит-системы 09"].price == Decimal("11500")
    assert by_name["Монтаж сплит-системы 18"].price == Decimal("14500")
    assert by_name["Трасса фреоновая"].price == Decimal("800")
    assert by_name["Трасса фреоновая"].unit == "м"
    assert by_name["Штроба (бетон)"].price == Decimal("1500")
    assert by_name["Чистка с дезинфекцией"].price == Decimal("4500")

    # Комплекты ссылаются на реальные позиции, формат items — по спецификации
    valid_ids = {item.id for item in items}
    for bundle in bundles:
        assert bundle.items, f"Комплект «{bundle.name}» пуст"
        for part in bundle.items:
            assert set(part) == {"price_item_id", "qty_default", "ask_qty"}
            assert part["price_item_id"] in valid_ids
            assert isinstance(part["ask_qty"], bool)

    # В стандартном монтаже трасса — 3 м по умолчанию и «спрашивать количество»
    standard = next(b for b in bundles if b.name == "Стандартный монтаж 07/09")
    track = next(
        p for p in standard.items
        if p["price_item_id"] == by_name["Трасса фреоновая"].id
    )
    assert track["qty_default"] == 3
    assert track["ask_qty"] is True


def test_seed_refuses_to_duplicate(session, user):
    seed_hvac(session, user.id)
    session.commit()
    with pytest.raises(RuntimeError, match="уже есть"):
        seed_hvac(session, user.id)


def test_seed_unknown_user(session):
    with pytest.raises(ValueError, match="не найден"):
        seed_hvac(session, 424242)

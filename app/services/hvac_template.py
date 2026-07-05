"""Шаблон ниши «кондиционерщик»: прайс (13 позиций) и 5 комплектов.

Используется онбордингом (POST /pricelist/seed) и CLI-скриптом
scripts/seed_hvac.py. Повторное применение для того же пользователя
не дублирует данные: если у него уже есть hvac-позиции — RuntimeError.
"""
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Bundle, PriceItem, User

# (название, синонимы для парсера, единица, цена)
PRICE_ITEMS: list[tuple[str, list[str], str, Decimal]] = [
    ("Монтаж сплит-системы 07", ["монтаж 07", "семерка", "семёрка"], "шт", Decimal("11500")),
    ("Монтаж сплит-системы 09", ["монтаж 09", "девятка", "монтаж девятки"], "шт", Decimal("11500")),
    ("Монтаж сплит-системы 12", ["монтаж 12", "двенашка", "двенадцатка"], "шт", Decimal("12500")),
    ("Монтаж сплит-системы 18", ["монтаж 18", "восемнашка"], "шт", Decimal("14500")),
    ("Трасса фреоновая", ["трасса", "магистраль", "фреонка"], "м", Decimal("800")),
    ("Штроба (бетон)", ["штроба бетон", "штробление бетона"], "м", Decimal("1500")),
    ("Штроба (кирпич)", ["штроба кирпич", "штробление кирпича"], "м", Decimal("1000")),
    ("Помпа дренажная", ["помпа", "дренажная помпа"], "шт", Decimal("7500")),
    ("Кронштейны с установкой", ["кронштейны", "кронштейн"], "компл", Decimal("1500")),
    ("Пробивка отверстия", ["пробивка", "отверстие в стене"], "шт", Decimal("1500")),
    ("Демонтаж кондиционера", ["демонтаж"], "шт", Decimal("2500")),
    ("Чистка с дезинфекцией", ["чистка", "дезинфекция", "профилактика"], "шт", Decimal("4500")),
    ("Дозаправка фреоном", ["дозаправка", "заправка", "заправка фреоном"], "шт", Decimal("3500")),
]

# Состав стандартного монтажа: монтаж + 3 м трассы (спросить количество)
# + кронштейны + пробивка. Для 07/09 берём позицию «09» — цена одинаковая.
_STANDARD = [
    ("Трасса фреоновая", 3, True),
    ("Кронштейны с установкой", 1, False),
    ("Пробивка отверстия", 1, False),
]

# (название комплекта, [(название позиции, qty_default, ask_qty), ...])
BUNDLES: list[tuple[str, list[tuple[str, int, bool]]]] = [
    ("Стандартный монтаж 07/09", [("Монтаж сплит-системы 09", 1, False), *_STANDARD]),
    ("Стандартный монтаж 12", [("Монтаж сплит-системы 12", 1, False), *_STANDARD]),
    ("Стандартный монтаж 18", [("Монтаж сплит-системы 18", 1, False), *_STANDARD]),
    (
        "Переезд кондиционера",
        [
            ("Демонтаж кондиционера", 1, False),
            ("Монтаж сплит-системы 09", 1, False),
            ("Трасса фреоновая", 3, True),
        ],
    ),
    ("Чистка + профилактика", [("Чистка с дезинфекцией", 1, False)]),
]


def seed_hvac(session: Session, user_id: int) -> tuple[int, int]:
    """Создаёт прайс и комплекты ниши hvac. Возвращает (позиций, комплектов)."""
    if session.get(User, user_id) is None:
        raise ValueError(f"Пользователь id={user_id} не найден")

    existing = session.scalar(
        select(func.count())
        .select_from(PriceItem)
        .where(PriceItem.user_id == user_id, PriceItem.niche == "hvac")
    )
    if existing:
        raise RuntimeError(
            f"У пользователя id={user_id} уже есть {existing} hvac-позиций — "
            "сид не перезаписывает существующий прайс"
        )

    item_ids: dict[str, int] = {}
    for i, (name, synonyms, unit, price) in enumerate(PRICE_ITEMS):
        item = PriceItem(
            user_id=user_id,
            niche="hvac",
            name=name,
            synonyms=synonyms,
            unit=unit,
            price=price,
            sort=(i + 1) * 10,
        )
        session.add(item)
        session.flush()  # получаем id для сборки комплектов
        item_ids[name] = item.id

    for i, (bundle_name, parts) in enumerate(BUNDLES):
        session.add(
            Bundle(
                user_id=user_id,
                name=bundle_name,
                sort=(i + 1) * 10,
                items=[
                    {
                        "price_item_id": item_ids[part_name],
                        "qty_default": qty_default,
                        "ask_qty": ask_qty,
                    }
                    for part_name, qty_default, ask_qty in parts
                ],
            )
        )

    return len(PRICE_ITEMS), len(BUNDLES)

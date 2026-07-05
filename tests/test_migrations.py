"""Миграции: накатываются, откатываются (downgrade полный) и накатываются повторно."""
from alembic import command
from sqlalchemy import create_engine, inspect

from tests.conftest import alembic_config

EXPECTED_TABLES = {
    "users",
    "profiles",
    "price_items",
    "bundles",
    "documents",
    "subscriptions",
    "usage_counters",
    "parse_logs",
}


def get_tables(db_url: str) -> set[str]:
    engine = create_engine(db_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_downgrade_upgrade(temp_db_url):
    cfg = alembic_config(temp_db_url)

    # Накат: все таблицы ядра на месте
    command.upgrade(cfg, "head")
    tables = get_tables(temp_db_url)
    assert EXPECTED_TABLES <= tables, f"Не хватает таблиц: {EXPECTED_TABLES - tables}"

    # Полный откат: остаётся только служебная alembic_version
    command.downgrade(cfg, "base")
    assert get_tables(temp_db_url) <= {"alembic_version"}

    # Повторный накат после отката проходит без ошибок
    command.upgrade(cfg, "head")
    assert EXPECTED_TABLES <= get_tables(temp_db_url)

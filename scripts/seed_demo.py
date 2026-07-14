"""Демо-пользователь локального стенда: телефон +79990000000, профиль
«Демо Мастер», прайс из шаблона «кондиционерщик». Идемпотентен.

Запуск: docker compose exec api python scripts/seed_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Profile, User
from app.services.hvac_template import seed_hvac

DEMO_PHONE = "+79990000000"


def main() -> None:
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.phone == DEMO_PHONE))
        if user is None:
            user = User(phone=DEMO_PHONE)
            session.add(user)
            session.flush()

        if session.get(Profile, user.id) is None:
            session.add(
                Profile(
                    user_id=user.id,
                    brand_name="Демо Мастер",
                    full_name="Демонстрационный Мастер Тестович",
                    inn="272000000000",
                    requisites={"text": "р/с 40802810000000000000, Демо Банк"},
                )
            )

        try:
            items, bundles = seed_hvac(session, user.id)
            seeded = f"прайс: {items} позиций, {bundles} комплектов"
        except RuntimeError:
            seeded = "прайс уже заполнен"

        session.commit()
        print(f"Демо-пользователь готов: {DEMO_PHONE} ({seeded})")


if __name__ == "__main__":
    main()

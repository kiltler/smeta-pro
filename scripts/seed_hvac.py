"""CLI-обёртка сида «кондиционерщик» (логика — в app/services/hvac_template.py).

Запуск в контейнере:
    docker compose exec api python scripts/seed_hvac.py <user_id>
"""
import sys
from pathlib import Path

# Скрипт запускается и как файл (python scripts/seed_hvac.py), и как модуль —
# добавляем корень проекта в путь импорта
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from app.services.hvac_template import seed_hvac


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print("Использование: python scripts/seed_hvac.py <user_id>")
        sys.exit(1)

    user_id = int(sys.argv[1])
    with SessionLocal() as session:
        try:
            items, bundles = seed_hvac(session, user_id)
        except (ValueError, RuntimeError) as e:
            print(f"Ошибка: {e}")
            sys.exit(1)
        session.commit()
    print(f"Готово: пользователю id={user_id} создано позиций — {items}, комплектов — {bundles}")


if __name__ == "__main__":
    main()

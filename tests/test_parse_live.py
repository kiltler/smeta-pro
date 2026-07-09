"""Живой смок-тест парсера с реальным ключом Anthropic.

Запускается только при заданном ANTHROPIC_API_KEY:
    docker compose exec api pytest tests/test_parse_live.py -v
"""
import os

import pytest

from app.services import parser

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="нужен реальный ANTHROPIC_API_KEY (живой смок-тест)",
)


@pytest.fixture
def seeded_client(auth_client):
    auth_client.post("/pricelist/seed")
    return auth_client


def test_live_parse_classic_dictation(seeded_client):
    """Ключевая диктовка из CLAUDE.md, реальный вызов модели."""
    resp = seeded_client.post(
        "/parse", json={"text": "монтаж девятки, трасса 4 метра, штроба бетон 2 метра, помпа"}
    )
    assert resp.status_code == 200
    result = resp.json()

    by_name = {p["name"]: p for p in result["positions"]}
    assert by_name["Монтаж сплит-системы 09"]["qty"] == 1
    assert by_name["Трасса фреоновая"]["qty"] == 4
    assert by_name["Штроба (бетон)"]["qty"] == 2
    assert by_name["Помпа дренажная"]["qty"] == 1
    assert result["unrecognized"] == []


def test_live_eval_full_dataset(seeded_client):
    """Прогон всего датасета через реальную модель; допускаем 1 промах из 10."""
    cases = parser.load_dataset()
    failures = []
    for case in cases:
        result = seeded_client.post("/parse", json={"text": case["text"]}).json()
        got = {(p["name"], p["qty"]) for p in result["positions"]}
        expected_items = {(e["name"], e["qty"]) for e in case["expected"]["items"]}
        if case["expected"]["bundles"]:
            continue  # комплекты сверяются в mock-тестах; здесь — прямые позиции
        if got != expected_items:
            failures.append(f"{case['text']!r}: ожидалось {expected_items}, получено {got}")

    assert len(failures) <= 1, "\n".join(failures)

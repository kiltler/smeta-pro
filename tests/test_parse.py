"""ИИ-парсер: 10 эталонных диктовок из датасета → ожидаемый JSON (модель замокана),
логирование в parse_logs, фиксация правок, изоляция и ошибки."""
import json
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import ParseLog
from app.services import parser
from app.services.hvac_template import PRICE_ITEMS


@pytest.fixture
def seeded_client(auth_client):
    auth_client.post("/pricelist/seed")
    return auth_client


@pytest.fixture
def mock_model(monkeypatch):
    """Подменяет вызов Anthropic API: тест сам задаёт ответ «модели»."""
    replies: list[dict] = []

    def fake_call(system_prompt, user_message):
        assert "Каталог позиций" in user_message  # каталог реально уходит в промпт
        return replies.pop(0)

    monkeypatch.setattr(parser, "_call_model", fake_call)
    return replies


def test_dataset_has_at_least_10_cases():
    assert len(parser.load_dataset()) >= 10


def test_all_dataset_cases_match_catalog(seeded_client, mock_model):
    """Каждая диктовка датасета: ответ модели → ожидаемые позиции с ценами из прайса."""
    prices = {name: price for name, _, _, price in PRICE_ITEMS}
    pricelist = {i["name"]: i for i in seeded_client.get("/pricelist").json()}
    bundles = {b["name"]: b for b in seeded_client.get("/bundles").json()}

    for case in parser.load_dataset():
        mock_model.append(case["expected"])
        resp = seeded_client.post("/parse", json={"text": case["text"]})
        assert resp.status_code == 200, case["text"]
        result = resp.json()

        # ожидаемые позиции: явные items + раскрытые комплекты
        expected_qty: dict[str, float] = {}
        for entry in case["expected"]["items"]:
            expected_qty[entry["name"]] = expected_qty.get(entry["name"], 0) + entry["qty"]
        for entry in case["expected"]["bundles"]:
            for part in bundles[entry["name"]]["items"]:
                item_name = next(
                    n for n, i in pricelist.items() if i["id"] == part["price_item_id"]
                )
                expected_qty[item_name] = (
                    expected_qty.get(item_name, 0) + part["qty_default"] * entry["qty"]
                )

        got = {p["name"]: p for p in result["positions"]}
        assert set(got) == set(expected_qty), case["text"]
        for name, qty in expected_qty.items():
            assert got[name]["qty"] == qty, f"{case['text']}: {name}"
            assert Decimal(got[name]["price"]) == prices[name]
        assert result["unrecognized"] == case["expected"]["unrecognized"], case["text"]


def test_parse_writes_log_and_correction(seeded_client, mock_model, db_session):
    mock_model.append(
        {"items": [{"name": "Помпа дренажная", "qty": 1}], "bundles": [], "unrecognized": []}
    )
    resp = seeded_client.post("/parse", json={"text": "помпа"})
    log_id = resp.json()["parse_log_id"]

    log = db_session.get(ParseLog, log_id)
    assert log.raw_input == "помпа"
    assert log.parsed_json["positions"][0]["name"] == "Помпа дренажная"
    assert log.corrected_json is None

    # пользователь поправил количество на экране проверки
    corrected = {"positions": [{**log.parsed_json["positions"][0], "qty": 2}]}
    assert seeded_client.put(f"/parse/{log_id}", json=corrected).status_code == 200
    db_session.refresh(log)
    assert log.corrected_json["positions"][0]["qty"] == 2


def test_unknown_model_name_goes_to_unrecognized(seeded_client, mock_model):
    """Модель сматчила несуществующее название — не падаем, отдаём в unrecognized."""
    mock_model.append(
        {"items": [{"name": "Позиция-галлюцинация", "qty": 1}], "bundles": [], "unrecognized": []}
    )
    result = seeded_client.post("/parse", json={"text": "что-то"}).json()
    assert result["positions"] == []
    assert result["unrecognized"] == ["Позиция-галлюцинация"]


def test_duplicate_items_are_merged(seeded_client, mock_model):
    mock_model.append(
        {
            "items": [
                {"name": "Трасса фреоновая", "qty": 3},
                {"name": "Трасса фреоновая", "qty": 2},
            ],
            "bundles": [],
            "unrecognized": [],
        }
    )
    result = seeded_client.post("/parse", json={"text": "трасса 3 и ещё 2"}).json()
    assert len(result["positions"]) == 1
    assert result["positions"][0]["qty"] == 5


def test_parse_without_key_returns_503(seeded_client):
    # _call_model не замокан, ключа в тестовом окружении нет
    resp = seeded_client.post("/parse", json={"text": "монтаж девятки"})
    assert resp.status_code == 503


def test_correction_of_foreign_log_is_404(seeded_client, mock_model, db_session):
    from app.models import User
    from app.services.auth import create_access_token

    mock_model.append({"items": [], "bundles": [], "unrecognized": []})
    log_id = seeded_client.post("/parse", json={"text": "тест"}).json()["parse_log_id"]

    stranger = User(phone="+79148887766")
    db_session.add(stranger)
    db_session.commit()
    seeded_client.headers["Authorization"] = f"Bearer {create_access_token(stranger.id)}"
    resp = seeded_client.put(f"/parse/{log_id}", json={"positions": []})
    assert resp.status_code == 404


def test_prompt_contains_few_shot_examples():
    prompt = parser.build_system_prompt()
    assert "{{EXAMPLES}}" not in prompt
    assert "монтаж девятки" in prompt  # первая диктовка датасета попала в примеры
    assert json.dumps("Монтаж сплит-системы 09", ensure_ascii=False)[1:-1] in prompt

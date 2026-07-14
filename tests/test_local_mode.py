"""Локальный режим: dev-код входа, мок-биллинг, мок-парсер, админка."""
import pytest
from sqlalchemy import select

from app.config import settings
from app.models import Subscription


# ---------- AUTH_DEV_CODE ----------

def test_dev_code_login(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_dev_code", "0000")
    resp = client.post(
        "/auth/verify", json={"phone": "+79990000000", "code": "0000"}
    )
    assert resp.status_code == 200  # вход без request-code, юзер создан

    # неверный код по-прежнему отбивается
    resp = client.post("/auth/verify", json={"phone": "+79990000000", "code": "1234"})
    assert resp.status_code == 400


def test_dev_code_disabled_by_default(client):
    resp = client.post("/auth/verify", json={"phone": "+79990000001", "code": "0000"})
    assert resp.status_code == 400  # dev-код выключен — обычная проверка


# ---------- MOCK_BILLING ----------

def test_mock_billing_activates_pro_instantly(auth_client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "mock_billing", True)
    resp = auth_client.post("/billing/subscribe")
    assert resp.status_code == 200
    assert resp.json()["confirmation_url"] == settings.billing_return_url

    state = auth_client.get("/billing/subscription").json()
    assert state["plan"] == "pro"
    assert state["documents_limit"] is None

    # отмена работает и в мок-режиме
    assert auth_client.post("/billing/cancel").json()["cancel_at_period_end"] is True


def test_mock_billing_renewal(auth_client, db_session, monkeypatch):
    from datetime import datetime, timedelta, timezone

    monkeypatch.setattr(settings, "mock_billing", True)
    auth_client.post("/billing/subscribe")
    sub = db_session.get(Subscription, auth_client.user_id)
    sub.period_end = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    state = auth_client.get("/billing/subscription").json()  # ленивое «продление»
    assert state["plan"] == "pro"
    db_session.refresh(sub)
    assert sub.period_end > datetime.now(timezone.utc) + timedelta(days=29)


# ---------- PARSE_ENABLED=mock ----------

@pytest.fixture
def mock_parse_client(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "parse_enabled", "mock")
    auth_client.post("/pricelist/seed")
    return auth_client


def test_mock_parse_synonyms_and_numbers(mock_parse_client):
    result = mock_parse_client.post(
        "/parse", json={"text": "монтаж девятки, трасса 4 метра, помпа"}
    ).json()
    got = {p["name"]: p["qty"] for p in result["positions"]}
    assert got == {
        "Монтаж сплит-системы 09": 1,
        "Трасса фреоновая": 4,
        "Помпа дренажная": 1,
    }
    assert result["unrecognized"] == []


def test_mock_parse_number_words_and_unrecognized(mock_parse_client):
    result = mock_parse_client.post(
        "/parse", json={"text": "штроба бетон полтора метра и вакуумация трассы"}
    ).json()
    got = {p["name"]: p["qty"] for p in result["positions"]}
    assert got["Штроба (бетон)"] == 1.5
    assert any("вакуумация" in u for u in result["unrecognized"])


def test_mock_parse_bundle_by_name(mock_parse_client):
    result = mock_parse_client.post(
        "/parse", json={"text": "стандартный монтаж 12"}
    ).json()
    names = {p["name"] for p in result["positions"]}
    # комплект раскрыт в позиции
    assert "Монтаж сплит-системы 12" in names
    assert "Трасса фреоновая" in names


def test_mock_parse_works_without_api_key(mock_parse_client, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    resp = mock_parse_client.post("/parse", json={"text": "фреонка 7 метров"})
    assert resp.status_code == 200
    assert resp.json()["positions"][0]["qty"] == 7


def test_mock_parse_writes_parse_log(mock_parse_client, db_session):
    from app.models import ParseLog

    log_id = mock_parse_client.post("/parse", json={"text": "помпа"}).json()["parse_log_id"]
    assert db_session.get(ParseLog, log_id).raw_input == "помпа"


# ---------- /admin ----------

def test_admin_disabled_without_password(client):
    assert client.get("/admin").status_code == 404


def test_admin_requires_auth_and_shows_metrics(client, auth_client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_user", "admin")
    monkeypatch.setattr(settings, "admin_password", "secret")

    assert client.get("/admin").status_code == 401
    assert client.get("/admin", auth=("admin", "wrong")).status_code == 401

    # данные: юзер + смета + Pro-подписка
    from app import storage

    storage.ensure_bucket()
    auth_client.post(
        "/documents/estimate",
        json={"positions": [{"name": "Чистка", "unit": "шт", "price": "4500", "qty": 1}]},
    )
    monkeypatch.setattr(settings, "mock_billing", True)
    auth_client.post("/billing/subscribe")

    page = client.get("/admin", auth=("admin", "secret"))
    assert page.status_code == 200
    assert "пользователей всего" in page.text
    assert "+79140000042" in page.text          # телефон юзера в списке
    assert ">pro<" in page.text                  # тариф подсвечен
    assert "конверсия Free→Pro" in page.text

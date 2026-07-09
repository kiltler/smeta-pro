"""Договор и акт из согласованной сметы: снапшот, PDF, НПД-формулировки,
статус «оплачено» и валидации."""
import re

import pytest
from sqlalchemy import select

from app import storage
from app.models import Document, Profile, User
from app.services import documents as doc_service
from app.services.documents import rubles_in_words

CLIENT_PERSON = {
    "type": "person",
    "name": "Анна Петровна Смирнова",
    "address": "г. Хабаровск, пер. Дежнёва 12, кв. 5",
    "phone": "+7 914 555-66-77",
}
CLIENT_COMPANY = {
    "type": "company",
    "name": "ООО «Тёплый дом»",
    "inn": "2721234567",
    "address": "г. Хабаровск, ул. Ленина 57, офис 3",
    "phone": "+7 4212 45-67-89",
}


@pytest.fixture
def approved_estimate(auth_client, client):
    """Смета, согласованная клиентом по публичной ссылке."""
    storage.ensure_bucket()
    auth_client.put(
        "/profile",
        json={
            "brand_name": "КлиматДВ",
            "full_name": "Аношкин Никита Алексеевич",
            "inn": "272012345678",
            "requisites": {"text": "р/с 40802810000000000001, Дальбанк"},
        },
    )
    estimate = auth_client.post(
        "/documents/estimate",
        json={
            "positions": [
                {"name": "Монтаж сплит-системы 09", "unit": "шт", "price": "11500", "qty": 1},
                {"name": "Трасса фреоновая", "unit": "м", "price": "800", "qty": 4},
            ]
        },
    ).json()
    client.post(f"/e/{estimate['public_uuid']}/approve")
    return estimate


def make_contract_act(auth_client, estimate, client_data=CLIENT_PERSON):
    return auth_client.post(
        f"/documents/{estimate['id']}/contract-act",
        json={"client": client_data, "work_deadline": "до 25.07.2026"},
    )


def test_contract_and_act_created(auth_client, approved_estimate, db_session):
    resp = make_contract_act(auth_client, approved_estimate)
    assert resp.status_code == 201, resp.text
    result = resp.json()

    for key, doc_type in [("contract", "contract"), ("act", "act")]:
        doc = result[key]
        assert doc["type"] == doc_type
        assert doc["parent_id"] == approved_estimate["id"]
        assert doc["total"] == approved_estimate["total"]
        assert doc["client_name"] == CLIENT_PERSON["name"]
        assert doc["public_uuid"] is None  # публичной ссылки у договора/акта нет

        row = db_session.get(Document, doc["id"])
        assert row.payload["positions"] == db_session.get(
            Document, approved_estimate["id"]
        ).payload["positions"]
        data, content_type = storage.get_object(row.pdf_key)
        assert data.startswith(b"%PDF") and content_type == "application/pdf"

    # выдача PDF через API
    assert auth_client.get(f"/documents/{result['contract']['id']}/pdf").content[:4] == b"%PDF"


def test_contract_html_npd_wording(auth_client, approved_estimate, db_session):
    """Обязательные НПД-формулировки и ключевые условия в тексте договора."""
    make_contract_act(auth_client, approved_estimate)
    contract = db_session.scalar(select(Document).where(Document.type == "contract"))
    act = db_session.scalar(select(Document).where(Document.type == "act"))
    user = db_session.get(User, contract.user_id)
    profile = db_session.get(Profile, contract.user_id)

    # переносы строк в шаблоне не должны ломать сверку фраз
    html = re.sub(r"\s+", " ", doc_service.render_contract_html(contract, act, profile, user))
    for fragment in [
        "Налог на профессиональный доход",       # обязательная НПД-фраза
        "422-ФЗ",
        "не является плательщиком НДС",
        "Мой налог",
        "по поручению и за счёт Заказчика",       # материалы — без перепродажи
        "подтверждающих документов",
        "12 (двенадцать) месяцев",                # гарантия
        "3 (трёх) рабочих дней",                  # мотивированный отказ
        "на основании подписанного",              # оплата по акту
        f"смет",                                  # ссылка на смету-приложение
        f"№ {approved_estimate['id']}",
        "Приложение № 1",
        "пер. Дежнёва 12",                        # адрес объекта
        "до 25.07.2026",                          # срок
        "Анна Петровна Смирнова",
        "Аношкин Никита Алексеевич",
        "ИНН 272012345678",
        "14 700",                                 # цена = итог сметы
        "четырнадцать тысяч семьсот рублей",      # сумма прописью
        "самостоятельно определяет способы",      # анти-переквалификация
    ]:
        assert fragment in html, fragment

    # язык результата, не процесса: никаких трудовых формулировок
    for banned in ["оклад", "график работы", "должност", "подчинени", "трудово"]:
        assert banned not in html.lower(), banned


def test_act_html_wording(auth_client, approved_estimate, db_session):
    make_contract_act(auth_client, approved_estimate)
    contract = db_session.scalar(select(Document).where(Document.type == "contract"))
    act = db_session.scalar(select(Document).where(Document.type == "act"))
    user = db_session.get(User, act.user_id)
    profile = db_session.get(Profile, act.user_id)

    html = re.sub(r"\s+", " ", doc_service.render_act_html(contract, act, profile, user))
    for fragment in [
        f"АКТ ВЫПОЛНЕННЫХ РАБОТ № {act.id}",
        f"Договору подряда № {contract.id}",
        "в полном объёме",
        "претензий по объёму, качеству и срокам выполнения работ не имеет",
        "Монтаж сплит-системы 09",
        "Трасса фреоновая",
        "14 700",
        "Налог на профессиональный доход",
    ]:
        assert fragment in html, fragment


def test_company_client_contract(auth_client, approved_estimate, db_session):
    resp = make_contract_act(auth_client, approved_estimate, CLIENT_COMPANY)
    assert resp.status_code == 201
    contract = db_session.scalar(select(Document).where(Document.type == "contract"))
    act = db_session.scalar(select(Document).where(Document.type == "act"))
    user = db_session.get(User, contract.user_id)
    html = doc_service.render_contract_html(
        contract, act, db_session.get(Profile, contract.user_id), user
    )
    assert "ООО «Тёплый дом»" in html
    assert "ИНН 2721234567" in html


def test_company_requires_inn(auth_client, approved_estimate):
    bad = {**CLIENT_COMPANY, "inn": None}
    resp = make_contract_act(auth_client, approved_estimate, bad)
    assert resp.status_code == 422
    assert "ИНН" in resp.text


def test_contract_requires_approved_estimate(auth_client):
    storage.ensure_bucket()
    draft = auth_client.post(
        "/documents/estimate",
        json={"positions": [{"name": "Тест", "unit": "шт", "price": "100", "qty": 1}]},
    ).json()
    resp = make_contract_act(auth_client, draft)
    assert resp.status_code == 400
    assert "согласовать" in resp.json()["detail"]


def test_contract_act_created_once(auth_client, approved_estimate):
    assert make_contract_act(auth_client, approved_estimate).status_code == 201
    resp = make_contract_act(auth_client, approved_estimate)
    assert resp.status_code == 409


def test_mark_paid_flow(auth_client, approved_estimate):
    resp = auth_client.post(f"/documents/{approved_estimate['id']}/mark-paid")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"
    # идемпотентно
    assert auth_client.post(f"/documents/{approved_estimate['id']}/mark-paid").json()[
        "status"
    ] == "paid"


def test_mark_paid_requires_approval(auth_client):
    storage.ensure_bucket()
    draft = auth_client.post(
        "/documents/estimate",
        json={"positions": [{"name": "Тест", "unit": "шт", "price": "100", "qty": 1}]},
    ).json()
    resp = auth_client.post(f"/documents/{draft['id']}/mark-paid")
    assert resp.status_code == 400


def test_rubles_in_words():
    assert rubles_in_words("14700") == "четырнадцать тысяч семьсот рублей"
    assert rubles_in_words("1") == "один рубль"
    assert rubles_in_words("22") == "двадцать два рубля"
    assert rubles_in_words("2000") == "две тысячи рублей"
    assert rubles_in_words("311111") == (
        "триста одиннадцать тысяч сто одиннадцать рублей"
    )
    assert rubles_in_words("17700.50") == "семнадцать тысяч семьсот рублей 50 копеек"

"""Смета: снапшот, PDF, публичная ссылка со статусами, срок жизни, дублирование."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import storage
from app.models import Document
from app.services import documents as doc_service

POSITIONS = [
    {"name": "Монтаж сплит-системы 09", "unit": "шт", "price": "11500", "qty": 1},
    {"name": "Трасса фреоновая", "unit": "м", "price": "800", "qty": 4},
]
TOTAL = "14700.00"  # 11500 + 800*4


@pytest.fixture
def estimate(auth_client):
    storage.ensure_bucket()
    resp = auth_client.post(
        "/documents/estimate",
        json={"positions": POSITIONS, "client_name": "Сергей, ул. Ленина 5"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_estimate_snapshot_and_pdf(auth_client, estimate, db_session):
    assert estimate["status"] == "draft"
    assert Decimal(estimate["total"]) == Decimal(TOTAL)

    document = db_session.get(Document, estimate["id"])
    # payload — снапшот с посчитанными суммами
    assert document.payload["positions"][1]["amount"] == "3200.00"
    assert document.payload["client_name"] == "Сергей, ул. Ленина 5"
    # срок действия — 14 дней
    ttl = document.expires_at - datetime.now(timezone.utc)
    assert timedelta(days=13, hours=23) < ttl < timedelta(days=14, minutes=5)
    # PDF лежит в хранилище и это настоящий PDF
    data, content_type = storage.get_object(document.pdf_key)
    assert data.startswith(b"%PDF") and content_type == "application/pdf"

    # авторизованная выдача PDF
    resp = auth_client.get(f"/documents/{estimate['id']}/pdf")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


def test_estimate_html_contains_key_fields(auth_client, estimate, db_session):
    """Смок содержимого: ключевые поля в HTML, из которого рендерится PDF."""
    auth_client.put(
        "/profile",
        json={"brand_name": "КлиматДВ", "full_name": "Иванов И.И.", "inn": "272012345678"},
    )
    document = db_session.get(Document, estimate["id"])
    profile = None
    from app.models import Profile

    profile = db_session.get(Profile, document.user_id)
    html = doc_service.render_estimate_html(document, profile)
    for fragment in [
        "КлиматДВ", "ИНН 272012345678", f"Смета № {document.id}",
        "Монтаж сплит-системы 09", "Трасса фреоновая", "4 м",
        "14 700", "действительна до", "Заказчик",
    ]:
        assert fragment in html, fragment


def test_snapshot_survives_price_change(auth_client, estimate):
    """Изменение прайса задним числом не меняет созданный документ."""
    item = auth_client.post(
        "/pricelist", json={"name": "Новая позиция", "unit": "шт", "price": "99999"}
    ).json()
    auth_client.put(f"/pricelist/{item['id']}", json={"price": "1"})
    docs = auth_client.get("/documents").json()
    assert docs[0]["total"] == TOTAL


def test_public_page_flow(client, auth_client, estimate):
    """Клиент без регистрации: просмотр → sent, «Согласовать» → approved."""
    url = f"/e/{estimate['public_uuid']}"

    page = client.get(url)  # клиент — неавторизованный client
    assert page.status_code == 200
    assert "Монтаж сплит-системы 09" in page.text
    assert "14 700" in page.text
    assert "Согласовать" in page.text

    # первое открытие: draft → sent
    assert auth_client.get("/documents").json()[0]["status"] == "sent"

    # согласование (форма делает POST + redirect на страницу)
    resp = client.post(f"{url}/approve", follow_redirects=True)
    assert resp.status_code == 200
    assert "согласована" in resp.text.lower()
    assert auth_client.get("/documents").json()[0]["status"] == "approved"

    # повторное согласование идемпотентно
    assert client.post(f"{url}/approve", follow_redirects=True).status_code == 200

    # публичный PDF без авторизации
    assert client.get(f"{url}/pdf").content.startswith(b"%PDF")


def test_public_page_unknown_uuid(client):
    assert client.get("/e/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/e/не-uuid").status_code == 404


def test_expired_link_is_410(client, auth_client, estimate, db_session):
    document = db_session.get(Document, estimate["id"])
    document.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    url = f"/e/{estimate['public_uuid']}"
    page = client.get(url)
    assert page.status_code == 410
    assert "истёк" in page.text
    assert client.post(f"{url}/approve").status_code == 410
    assert client.get(f"{url}/pdf").status_code == 410


def test_duplicate_estimate(auth_client, estimate):
    resp = auth_client.post(f"/documents/{estimate['id']}/duplicate")
    assert resp.status_code == 201
    copy = resp.json()
    assert copy["id"] != estimate["id"]
    assert copy["public_uuid"] != estimate["public_uuid"]
    assert copy["total"] == estimate["total"]
    assert copy["status"] == "draft"

    docs = auth_client.get("/documents").json()
    assert len(docs) == 2 and docs[0]["id"] == copy["id"]  # свежие сверху


def test_foreign_document_is_404(auth_client, estimate, db_session):
    from app.models import User
    from app.services.auth import create_access_token

    stranger = User(phone="+79141112233")
    db_session.add(stranger)
    db_session.commit()
    auth_client.headers["Authorization"] = f"Bearer {create_access_token(stranger.id)}"
    assert auth_client.get(f"/documents/{estimate['id']}/pdf").status_code == 404
    assert auth_client.post(f"/documents/{estimate['id']}/duplicate").status_code == 404


def test_estimate_requires_positions(auth_client):
    resp = auth_client.post("/documents/estimate", json={"positions": []})
    assert resp.status_code == 422


def test_set_client_name_later(auth_client, db_session):
    """Смета без имени → имя дописывается позже, PDF перегенерируется, ссылка та же."""
    storage.ensure_bucket()
    created = auth_client.post(
        "/documents/estimate", json={"positions": POSITIONS}
    ).json()
    assert created["client_name"] is None

    resp = auth_client.put(
        f"/documents/{created['id']}/client-name",
        json={"client_name": "Анна Петровна"},
    )
    assert resp.status_code == 200
    assert resp.json()["client_name"] == "Анна Петровна"
    assert resp.json()["public_uuid"] == created["public_uuid"]

    # имя попало в перегенерированный PDF-документ (проверяем через html-рендер)
    document = db_session.get(Document, created["id"])
    assert document.payload["client_name"] == "Анна Петровна"
    # снапшот позиций не тронут
    assert document.payload["total"] == TOTAL

    # у договора/акта имя не меняется этим эндпоинтом
    bad = auth_client.put("/documents/999999/client-name", json={"client_name": "X"})
    assert bad.status_code == 404

"""Прайс-лист: CRUD, шаблон из сида, чужие позиции недоступны."""
from decimal import Decimal

from sqlalchemy import select

from app.models import Bundle, User
from app.services.auth import create_access_token


def test_crud_flow(auth_client):
    assert auth_client.get("/pricelist").json() == []

    resp = auth_client.post(
        "/pricelist", json={"name": "Монтаж 09", "unit": "шт", "price": "11500"}
    )
    assert resp.status_code == 201
    item = resp.json()
    assert Decimal(item["price"]) == Decimal("11500")

    resp = auth_client.put(f"/pricelist/{item['id']}", json={"price": "12000"})
    assert resp.status_code == 200
    assert Decimal(resp.json()["price"]) == Decimal("12000")

    assert auth_client.delete(f"/pricelist/{item['id']}").status_code == 204
    assert auth_client.get("/pricelist").json() == []


def test_seed_endpoint(auth_client):
    resp = auth_client.post("/pricelist/seed")
    assert resp.status_code == 200
    assert resp.json() == {"created": True, "items": 13, "bundles": 5}
    assert len(auth_client.get("/pricelist").json()) == 13
    assert len(auth_client.get("/bundles").json()) == 5

    # повторный вызов не дублирует
    assert auth_client.post("/pricelist/seed").json()["created"] is False
    assert len(auth_client.get("/pricelist").json()) == 13


def test_delete_item_removes_it_from_bundles(auth_client, db_session):
    auth_client.post("/pricelist/seed")
    items = auth_client.get("/pricelist").json()
    track = next(i for i in items if i["name"] == "Трасса фреоновая")

    auth_client.delete(f"/pricelist/{track['id']}")

    bundles = db_session.scalars(select(Bundle)).all()
    for bundle in bundles:
        assert all(p["price_item_id"] != track["id"] for p in bundle.items)


def test_foreign_item_is_404(auth_client, db_session):
    stranger = User(phone="+79149999999")
    db_session.add(stranger)
    db_session.commit()

    resp = auth_client.post(
        "/pricelist", json={"name": "Моя позиция", "unit": "шт", "price": "100"}
    )
    item_id = resp.json()["id"]

    auth_client.headers["Authorization"] = f"Bearer {create_access_token(stranger.id)}"
    assert auth_client.get("/pricelist").json() == []
    assert auth_client.put(f"/pricelist/{item_id}", json={"price": "1"}).status_code == 404
    assert auth_client.delete(f"/pricelist/{item_id}").status_code == 404

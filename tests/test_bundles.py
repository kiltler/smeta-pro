"""Комплекты: конструктор, валидация ссылок на прайс, CRUD."""


def make_item(auth_client, name="Позиция", price="1000"):
    return auth_client.post(
        "/pricelist", json={"name": name, "unit": "шт", "price": price}
    ).json()


def test_bundle_crud(auth_client):
    a = make_item(auth_client, "Монтаж 09", "11500")
    b = make_item(auth_client, "Трасса", "800")

    resp = auth_client.post(
        "/bundles",
        json={
            "name": "Стандартный монтаж",
            "items": [
                {"price_item_id": a["id"], "qty_default": 1},
                {"price_item_id": b["id"], "qty_default": 3, "ask_qty": True},
            ],
        },
    )
    assert resp.status_code == 201
    bundle = resp.json()
    assert bundle["items"][1]["ask_qty"] is True

    # правка: другое количество трассы
    bundle["items"][1]["qty_default"] = 5
    resp = auth_client.put(f"/bundles/{bundle['id']}", json=bundle)
    assert resp.status_code == 200
    assert resp.json()["items"][1]["qty_default"] == 5

    assert auth_client.delete(f"/bundles/{bundle['id']}").status_code == 204
    assert auth_client.get("/bundles").json() == []


def test_bundle_rejects_foreign_or_missing_items(auth_client):
    a = make_item(auth_client)
    resp = auth_client.post(
        "/bundles",
        json={
            "name": "Битый комплект",
            "items": [
                {"price_item_id": a["id"], "qty_default": 1},
                {"price_item_id": 999999, "qty_default": 1},
            ],
        },
    )
    assert resp.status_code == 400
    assert "999999" in resp.json()["detail"]


def test_bundle_requires_items(auth_client):
    resp = auth_client.post("/bundles", json={"name": "Пустой", "items": []})
    assert resp.status_code == 422

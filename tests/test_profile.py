"""Профиль: чтение/запись полей, загрузка и получение логотипа."""
from app import storage

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f030005fe02fea72d994800000000494e44ae426082"
)


def test_profile_empty_then_update(auth_client):
    assert auth_client.get("/profile").json() == {
        "brand_name": None,
        "full_name": None,
        "inn": None,
        "requisites": {},
        "has_logo": False,
    }

    data = {
        "brand_name": "КлиматДВ",
        "full_name": "Иванов Иван Иванович",
        "inn": "272000000000",
        "requisites": {"text": "р/с 40802810..., Банк ..."},
    }
    resp = auth_client.put("/profile", json=data)
    assert resp.status_code == 200
    assert auth_client.get("/profile").json() == {**data, "has_logo": False}


def test_logo_upload_and_download(auth_client):
    storage.ensure_bucket()

    resp = auth_client.post(
        "/profile/logo", files={"file": ("logo.png", PNG_1PX, "image/png")}
    )
    assert resp.status_code == 200
    assert auth_client.get("/profile").json()["has_logo"] is True

    logo = auth_client.get("/profile/logo")
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/png"
    assert logo.content == PNG_1PX


def test_logo_wrong_type_rejected(auth_client):
    resp = auth_client.post(
        "/profile/logo", files={"file": ("virus.exe", b"MZ...", "application/x-msdownload")}
    )
    assert resp.status_code == 415


def test_logo_404_when_missing(auth_client):
    assert auth_client.get("/profile/logo").status_code == 404


def test_profile_requires_auth(client):
    assert client.get("/profile").status_code == 401

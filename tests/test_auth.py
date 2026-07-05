"""Вход по телефону: happy path, неверный/истёкший/повторный код, rate limit,
защита приватных роутов."""
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import AuthCode

PHONE = "+79141234567"


@pytest.fixture
def sent_codes(monkeypatch):
    """Перехватывает отправку SMS и складывает коды в список."""
    codes: list[str] = []

    def fake_send_sms(phone: str, text: str) -> None:
        codes.append(re.search(r"\d{4}", text).group())

    monkeypatch.setattr("app.services.auth.send_sms", fake_send_sms)
    return codes


def request_code(client, phone=PHONE):
    return client.post("/auth/request-code", json={"phone": phone})


def verify(client, code, phone=PHONE):
    return client.post("/auth/verify", json={"phone": phone, "code": code})


def test_happy_path(client, sent_codes):
    assert request_code(client).status_code == 200
    assert len(sent_codes) == 1 and len(sent_codes[0]) == 4

    resp = verify(client, sent_codes[0])
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["phone"] == PHONE


def test_phone_is_normalized(client, sent_codes):
    request_code(client, "8 (914) 123-45-67")  # тот же номер в другой записи
    resp = verify(client, sent_codes[0], PHONE)
    assert resp.status_code == 200


def test_wrong_code(client, sent_codes):
    request_code(client)
    wrong = "0000" if sent_codes[0] != "0000" else "1111"
    assert verify(client, wrong).status_code == 400
    # правильный код после неверной попытки всё ещё работает
    assert verify(client, sent_codes[0]).status_code == 200


def test_expired_code(client, sent_codes, db_session):
    request_code(client)
    auth_code = db_session.scalar(select(AuthCode).where(AuthCode.phone == PHONE))
    auth_code.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    assert verify(client, sent_codes[0]).status_code == 400


def test_code_cannot_be_reused(client, sent_codes):
    request_code(client)
    assert verify(client, sent_codes[0]).status_code == 200
    assert verify(client, sent_codes[0]).status_code == 400


def test_new_code_invalidates_previous(client, sent_codes):
    request_code(client)
    request_code(client)
    assert verify(client, sent_codes[0]).status_code == 400  # старый код погашен
    assert verify(client, sent_codes[1]).status_code == 200


def test_brute_force_attempts_limited(client, sent_codes):
    request_code(client)
    real = sent_codes[0]
    wrong = "0000" if real != "0000" else "1111"
    for _ in range(5):
        assert verify(client, wrong).status_code == 400
    # после 5 неверных попыток даже правильный код не принимается
    assert verify(client, real).status_code == 400


def test_rate_limit(client, sent_codes):
    for _ in range(3):
        assert request_code(client).status_code == 200
    assert request_code(client).status_code == 429
    # лимит не задевает другой номер
    assert request_code(client, "+79997654321").status_code == 200


def test_invalid_phone_rejected(client):
    assert request_code(client, "12345").status_code == 422


def test_private_route_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    bad = client.get("/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert bad.status_code == 401

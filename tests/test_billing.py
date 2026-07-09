"""Биллинг — приоритетные тесты («Деньги — священны»):
идемпотентный вебхук, лимит ровно на 4-м документе, водяной знак Free/Pro,
grace-период, отмена подписки."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app import storage
from app.models import BillingEvent, Document, Subscription
from app.services import billing
from app.services import documents as doc_service

NOW = lambda: datetime.now(timezone.utc)  # noqa: E731
POSITIONS = [{"name": "Чистка с дезинфекцией", "unit": "шт", "price": "4500", "qty": 1}]


@pytest.fixture
def fake_yookassa(monkeypatch):
    """Подменяет модульный клиент ЮKassa управляемой фальшивкой."""

    class Fake:
        def __init__(self):
            self.payments: dict[str, dict] = {}
            self.charges: list[dict] = []
            self.counter = 0

        def _new_id(self):
            self.counter += 1
            return f"pay_{self.counter:04d}"

        def create_payment(self, user_id):
            pid = self._new_id()
            self.payments[pid] = {
                "id": pid, "status": "pending",
                "metadata": {"user_id": str(user_id), "kind": "subscribe"},
            }
            return {"id": pid, "confirmation": {"confirmation_url": f"https://yookassa.test/{pid}"}}

        def charge(self, user_id, payment_method_id):
            pid = self._new_id()
            payment = {
                "id": pid, "status": "pending",
                "metadata": {"user_id": str(user_id), "kind": "renewal"},
                "payment_method": {"id": payment_method_id, "saved": True},
            }
            self.payments[pid] = payment
            self.charges.append(payment)
            return payment

        def get_payment(self, payment_id):
            return self.payments[payment_id]

        def succeed(self, pid, method_id="pm_123", saved=True):
            self.payments[pid]["status"] = "succeeded"
            self.payments[pid]["payment_method"] = {"id": method_id, "saved": saved}

    fake = Fake()
    monkeypatch.setattr(billing, "client", fake)
    return fake


def make_estimate(auth_client):
    storage.ensure_bucket()
    return auth_client.post("/documents/estimate", json={"positions": POSITIONS})


def webhook(client, event, pid):
    return client.post("/billing/webhook", json={"event": event, "object": {"id": pid}})


def make_pro(db_session, user_id, **kwargs):
    sub = Subscription(
        user_id=user_id, plan="pro", status=kwargs.pop("status", "active"),
        period_end=kwargs.pop("period_end", NOW() + timedelta(days=20)), **kwargs
    )
    db_session.add(sub)
    db_session.commit()
    return sub


# ---------- вебхук: идемпотентность ----------

def test_webhook_idempotent(client, auth_client, db_session, fake_yookassa):
    url = auth_client.post("/billing/subscribe").json()["confirmation_url"]
    pid = url.rsplit("/", 1)[1]
    fake_yookassa.succeed(pid)

    assert webhook(client, "payment.succeeded", pid).json()["result"] == "applied"
    sub = db_session.get(Subscription, auth_client.user_id)
    assert sub.plan == "pro" and sub.status == "active"
    assert sub.yookassa_payment_method_id == "pm_123"
    first_period_end = sub.period_end
    assert timedelta(days=29) < first_period_end - NOW() < timedelta(days=31)

    # повторная доставка того же события — no-op
    assert webhook(client, "payment.succeeded", pid).json()["result"] == "duplicate"
    db_session.refresh(sub)
    assert sub.period_end == first_period_end  # период не продлился дважды
    events = db_session.scalar(select(func.count()).select_from(BillingEvent))
    assert events == 1


def test_webhook_junk_is_rejected(client):
    assert client.post("/billing/webhook", json={"foo": "bar"}).status_code == 400


# ---------- лимит Free ----------

def test_free_limit_hits_on_fourth_document(auth_client):
    for i in range(3):
        assert make_estimate(auth_client).status_code == 201, f"смета {i + 1}"
    resp = make_estimate(auth_client)
    assert resp.status_code == 402
    assert "Pro снимает лимит" in resp.json()["detail"]

    state = auth_client.get("/billing/subscription").json()
    assert state["documents_used"] == 3 and state["documents_limit"] == 3


def test_duplicate_counts_towards_limit(auth_client):
    first = make_estimate(auth_client).json()
    assert auth_client.post(f"/documents/{first['id']}/duplicate").status_code == 201
    assert make_estimate(auth_client).status_code == 201  # третий
    assert auth_client.post(f"/documents/{first['id']}/duplicate").status_code == 402


def test_pro_has_no_limit(auth_client, db_session):
    make_pro(db_session, auth_client.user_id)
    for i in range(5):
        assert make_estimate(auth_client).status_code == 201, f"смета {i + 1}"
    state = auth_client.get("/billing/subscription").json()
    assert state["documents_limit"] is None


# ---------- водяной знак ----------

def test_watermark_on_free_absent_on_pro(auth_client, db_session):
    free_doc = db_session.get(Document, make_estimate(auth_client).json()["id"])
    assert free_doc.payload["watermark"] is True
    html = doc_service.render_estimate_html(free_doc, None)
    assert doc_service.WATERMARK_TEXT in html

    make_pro(db_session, auth_client.user_id)
    pro_doc = db_session.get(Document, make_estimate(auth_client).json()["id"])
    assert pro_doc.payload["watermark"] is False
    assert doc_service.WATERMARK_TEXT not in doc_service.render_estimate_html(pro_doc, None)


def test_watermark_in_contract_follows_plan(auth_client, client, db_session):
    estimate = make_estimate(auth_client).json()
    client.post(f"/e/{estimate['public_uuid']}/approve")
    auth_client.post(
        f"/documents/{estimate['id']}/contract-act",
        json={
            "client": {"type": "person", "name": "Анна", "address": "Хабаровск", "phone": "+7 914"},
            "work_deadline": "до 25.07.2026",
        },
    )
    contract = db_session.scalar(select(Document).where(Document.type == "contract"))
    act = db_session.scalar(select(Document).where(Document.type == "act"))
    from app.models import User

    user = db_session.get(User, contract.user_id)
    assert doc_service.WATERMARK_TEXT in doc_service.render_contract_html(contract, act, None, user)
    assert doc_service.WATERMARK_TEXT in doc_service.render_act_html(contract, act, None, user)


# ---------- grace-период ----------

def test_grace_keeps_pro_and_triggers_renewal(auth_client, db_session, fake_yookassa):
    make_pro(
        db_session, auth_client.user_id,
        period_end=NOW() - timedelta(days=1),
        yookassa_payment_method_id="pm_123",
    )
    state = auth_client.get("/billing/subscription").json()
    assert state["plan"] == "pro"  # grace: всё ещё Pro
    assert len(fake_yookassa.charges) == 1  # автосписание запущено

    # повторный запрос не создаёт второй платёж (идемпотентная попытка)
    auth_client.get("/billing/subscription")
    assert len(fake_yookassa.charges) == 1


def test_failed_renewal_goes_past_due_then_free(
    client, auth_client, db_session, fake_yookassa
):
    sub = make_pro(
        db_session, auth_client.user_id,
        period_end=NOW() - timedelta(days=1),
        yookassa_payment_method_id="pm_123",
    )
    auth_client.get("/billing/subscription")  # запускает автосписание
    pid = fake_yookassa.charges[0]["id"]
    fake_yookassa.payments[pid]["status"] = "canceled"

    assert webhook(client, "payment.canceled", pid).json()["result"] == "past_due"
    db_session.refresh(sub)
    assert sub.status == "past_due"
    assert auth_client.get("/billing/subscription").json()["plan"] == "pro"  # ещё grace

    # grace истёк → Free, данные на месте
    sub.period_end = NOW() - timedelta(days=4)
    db_session.commit()
    state = auth_client.get("/billing/subscription").json()
    assert state["plan"] == "free"
    assert auth_client.get("/documents").status_code == 200  # ничего не удалено


def test_successful_renewal_extends_period(client, auth_client, db_session, fake_yookassa):
    sub = make_pro(
        db_session, auth_client.user_id,
        period_end=NOW() - timedelta(days=1),
        yookassa_payment_method_id="pm_123",
    )
    auth_client.get("/billing/subscription")
    pid = fake_yookassa.charges[0]["id"]
    fake_yookassa.succeed(pid)
    assert webhook(client, "payment.succeeded", pid).json()["result"] == "applied"
    db_session.refresh(sub)
    assert sub.status == "active"
    assert sub.period_end > NOW() + timedelta(days=29)


# ---------- отмена ----------

def test_cancel_works_until_period_end_without_renewal(
    auth_client, db_session, fake_yookassa
):
    sub = make_pro(
        db_session, auth_client.user_id, yookassa_payment_method_id="pm_123"
    )
    state = auth_client.post("/billing/cancel").json()
    assert state["cancel_at_period_end"] is True
    assert state["plan"] == "pro"  # до конца оплаченного периода

    # период кончился: без grace и без автосписаний — сразу Free
    sub.period_end = NOW() - timedelta(hours=1)
    db_session.commit()
    assert auth_client.get("/billing/subscription").json()["plan"] == "free"
    assert fake_yookassa.charges == []

    # возобновление, пока период не истёк
    sub.period_end = NOW() + timedelta(days=10)
    sub.status = "canceled"
    db_session.commit()
    assert auth_client.post("/billing/resume").json()["cancel_at_period_end"] is False


def test_subscribe_returns_confirmation_url(auth_client, fake_yookassa):
    resp = auth_client.post("/billing/subscribe")
    assert resp.status_code == 200
    assert resp.json()["confirmation_url"].startswith("https://yookassa.test/")


def test_subscribe_unconfigured_is_503(auth_client):
    # реальный клиент без кредов ЮKassa
    assert auth_client.post("/billing/subscribe").status_code == 503

"""Биллинг: тарифы Free/Pro, ЮKassa, лимиты, grace-период.

Правила («Деньги — священны», CLAUDE.md):
- вебхуки идемпотентны: ключ события в billing_events, повтор — no-op;
- телу вебхука не доверяем: статус и метаданные перечитываются из API ЮKassa;
- продление ленивое (без крона): при обращении пользователя после period_end
  создаётся автосписание по сохранённому способу; попытка идемпотентна
  (тоже ключ в billing_events);
- grace-период 3 дня: Pro сохраняется, пока ждём/повторяем списание;
  после — эффективно Free, данные не удаляются;
- отмена = status 'canceled': работает до конца оплаченного периода,
  автосписаний больше нет.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BillingEvent, Subscription, UsageCounter, User

logger = logging.getLogger(__name__)

PERIOD_DAYS = 30
YOOKASSA_API = "https://api.yookassa.ru/v3"


class LimitExceeded(Exception):
    """Исчерпан лимит Free — фронт показывает пейволл."""


class BillingNotConfigured(Exception):
    """Не заданы креды ЮKassa."""


class YooKassaClient:
    """Тонкая обёртка над API ЮKassa. Тестовый/боевой режим различаются
    только кредами магазина в env. В тестах методы подменяются."""

    def _request(self, method: str, path: str, json_body: dict | None = None) -> dict:
        if not (settings.yookassa_shop_id and settings.yookassa_secret_key):
            raise BillingNotConfigured
        headers = {"Idempotence-Key": str(uuid.uuid4())} if json_body else {}
        resp = httpx.request(
            method,
            f"{YOOKASSA_API}{path}",
            json=json_body,
            headers=headers,
            auth=(settings.yookassa_shop_id, settings.yookassa_secret_key),
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def create_payment(self, user_id: int) -> dict:
        """Первый платёж подписки: редирект на оплату + сохранение способа."""
        return self._request(
            "POST",
            "/payments",
            {
                "amount": {"value": f"{settings.pro_price_rub}.00", "currency": "RUB"},
                "capture": True,
                "save_payment_method": True,
                "description": "СметаПро Pro — подписка на месяц",
                "confirmation": {"type": "redirect", "return_url": settings.billing_return_url},
                "metadata": {"user_id": str(user_id), "kind": "subscribe"},
            },
        )

    def charge(self, user_id: int, payment_method_id: str) -> dict:
        """Автосписание по сохранённому способу оплаты (продление)."""
        return self._request(
            "POST",
            "/payments",
            {
                "amount": {"value": f"{settings.pro_price_rub}.00", "currency": "RUB"},
                "capture": True,
                "payment_method_id": payment_method_id,
                "description": "СметаПро Pro — продление подписки",
                "metadata": {"user_id": str(user_id), "kind": "renewal"},
            },
        )

    def get_payment(self, payment_id: str) -> dict:
        return self._request("GET", f"/payments/{payment_id}")


client = YooKassaClient()  # модульный синглтон — тесты подменяют


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- идемпотентность ----------

def _claim_event(session: Session, key: str) -> bool:
    """True — ключ свободен и захвачен; False — событие уже обработано."""
    try:
        with session.begin_nested():
            session.add(BillingEvent(event_key=key))
        return True
    except IntegrityError:
        return False


# ---------- тариф ----------

def effective_plan(sub: Subscription | None, now: datetime | None = None) -> str:
    now = now or _now()
    if sub is None or sub.plan != "pro" or sub.period_end is None:
        return "free"
    if now < sub.period_end:
        return "pro"
    # период кончился: активным (и ожидающим повторного списания) даём grace
    if sub.status in ("active", "past_due"):
        if now < sub.period_end + timedelta(days=settings.billing_grace_days):
            return "pro"
    return "free"


def _maybe_start_renewal(session: Session, sub: Subscription) -> None:
    """Ленивое автосписание: период истёк, способ сохранён, попытка ещё не делалась."""
    now = _now()
    if (
        sub.status != "active"
        or sub.period_end is None
        or now < sub.period_end
        or now >= sub.period_end + timedelta(days=settings.billing_grace_days)
        or not sub.yookassa_payment_method_id
    ):
        return
    attempt_key = f"renewal:{sub.user_id}:{sub.period_end.date().isoformat()}"
    if not _claim_event(session, attempt_key):
        return
    try:
        payment = client.charge(sub.user_id, sub.yookassa_payment_method_id)
        session.commit()
        logger.info("Автосписание запущено: user=%s payment=%s", sub.user_id, payment.get("id"))
    except BillingNotConfigured:
        session.rollback()
    except Exception:
        session.rollback()
        logger.exception("Не удалось создать автосписание user=%s", sub.user_id)


def subscription_state(session: Session, user: User) -> dict:
    sub = session.get(Subscription, user.id)
    if sub is not None:
        _maybe_start_renewal(session, sub)
    now = _now()
    plan = effective_plan(sub, now)
    month = now.strftime("%Y-%m")
    counter = session.get(UsageCounter, (user.id, month))
    return {
        "plan": plan,
        "status": sub.status if sub else "none",
        "period_end": sub.period_end.isoformat() if sub and sub.period_end else None,
        "cancel_at_period_end": bool(sub and sub.status == "canceled"),
        "past_due": bool(sub and sub.status == "past_due" and plan == "pro"),
        "payment_method_saved": bool(sub and sub.yookassa_payment_method_id),
        "documents_used": counter.documents_created if counter else 0,
        "documents_limit": None if plan == "pro" else settings.free_doc_limit,
        "price_rub": settings.pro_price_rub,
    }


# ---------- лимит Free ----------

def ensure_can_create_document(session: Session, user: User) -> None:
    """Free: не больше FREE_DOC_LIMIT смет в календарный месяц."""
    sub = session.get(Subscription, user.id)
    if effective_plan(sub) == "pro":
        return
    month = _now().strftime("%Y-%m")
    counter = session.get(UsageCounter, (user.id, month))
    if counter is not None and counter.documents_created >= settings.free_doc_limit:
        raise LimitExceeded


def increment_usage(session: Session, user: User) -> None:
    month = _now().strftime("%Y-%m")
    counter = session.get(UsageCounter, (user.id, month))
    if counter is None:
        counter = UsageCounter(user_id=user.id, month=month, documents_created=0)
        session.add(counter)
    counter.documents_created += 1


def user_is_pro(session: Session, user: User) -> bool:
    return effective_plan(session.get(Subscription, user.id)) == "pro"


# ---------- подписка ----------

def start_subscription(session: Session, user: User) -> str:
    """Создаёт платёж ЮKassa, возвращает URL страницы оплаты."""
    payment = client.create_payment(user.id)
    logger.info("Создан платёж подписки: user=%s payment=%s", user.id, payment.get("id"))
    return payment["confirmation"]["confirmation_url"]


def cancel_subscription(session: Session, user: User) -> None:
    sub = session.get(Subscription, user.id)
    if sub is not None and sub.plan == "pro":
        sub.status = "canceled"
        session.commit()


def resume_subscription(session: Session, user: User) -> None:
    sub = session.get(Subscription, user.id)
    if sub is not None and sub.status == "canceled" and sub.period_end > _now():
        sub.status = "active"
        session.commit()


# ---------- вебхуки ----------

def handle_webhook(session: Session, event_type: str, payment_id: str) -> str:
    """Идемпотентная обработка вебхука. Возвращает результат для лога."""
    key = f"{event_type}:{payment_id}"
    if not _claim_event(session, key):
        return "duplicate"

    # телу вебхука не доверяем — перечитываем платёж из API
    payment = client.get_payment(payment_id)
    metadata = payment.get("metadata") or {}
    user_id = int(metadata.get("user_id", 0))
    if not user_id:
        session.commit()  # ключ фиксируем, чтобы мусор не долбился повторно
        return "no_user"

    if event_type == "payment.succeeded" and payment.get("status") == "succeeded":
        sub = session.get(Subscription, user_id)
        if sub is None:
            sub = Subscription(user_id=user_id)
            session.add(sub)
        now = _now()
        base = sub.period_end if (sub.period_end and sub.period_end > now) else now
        sub.plan = "pro"
        sub.status = "active"
        sub.period_end = base + timedelta(days=PERIOD_DAYS)
        method = payment.get("payment_method") or {}
        if method.get("saved") and method.get("id"):
            sub.yookassa_payment_method_id = method["id"]
        session.commit()
        logger.info("Подписка продлена: user=%s до %s", user_id, sub.period_end)
        return "applied"

    if event_type == "payment.canceled" and metadata.get("kind") == "renewal":
        sub = session.get(Subscription, user_id)
        if sub is not None and sub.plan == "pro" and sub.status == "active":
            sub.status = "past_due"  # grace уже идёт; после него — эффективно Free
        session.commit()
        logger.info("Автосписание не прошло: user=%s (grace)", user_id)
        return "past_due"

    session.commit()
    return "ignored"

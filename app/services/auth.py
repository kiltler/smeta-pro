"""Вход по телефону: одноразовые коды и JWT.

Правила:
- в БД хранится только HMAC-хэш кода;
- код живёт AUTH_CODE_TTL_MINUTES минут и одноразовый;
- новый запрос кода делает предыдущий недействительным (проверяется только последний);
- не больше AUTH_RATE_LIMIT_PER_HOUR запросов кода на номер в час;
- не больше MAX_VERIFY_ATTEMPTS попыток ввода на один код.
"""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuthCode, User
from app.services.sms import send_sms

MAX_VERIFY_ATTEMPTS = 5
JWT_ALGORITHM = "HS256"


class RateLimitExceeded(Exception):
    """Слишком много запросов кода на этот номер."""


class InvalidCode(Exception):
    """Код неверен, истёк, уже использован или исчерпаны попытки."""


class InvalidPhone(ValueError):
    """Телефон не похож на российский мобильный номер."""


def normalize_phone(raw: str) -> str:
    """Приводит телефон к формату +7XXXXXXXXXX (первая ниша — Россия)."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in "78":
        digits = "7" + digits[1:]
    elif len(digits) == 10 and digits[0] == "9":
        digits = "7" + digits
    else:
        raise InvalidPhone(f"Не удалось распознать номер телефона: {raw!r}")
    return f"+{digits}"


def _hash_code(phone: str, code: str) -> str:
    """HMAC, а не голый sha256: без SECRET_KEY хэш 4-значного кода перебирается мгновенно."""
    return hmac.new(
        settings.secret_key.encode(), f"{phone}:{code}".encode(), hashlib.sha256
    ).hexdigest()


def request_code(session: Session, phone: str) -> None:
    now = datetime.now(timezone.utc)

    recent = session.scalar(
        select(func.count())
        .select_from(AuthCode)
        .where(AuthCode.phone == phone, AuthCode.created_at > now - timedelta(hours=1))
    )
    if recent >= settings.auth_rate_limit_per_hour:
        raise RateLimitExceeded

    code = f"{secrets.randbelow(10_000):04d}"
    session.add(
        AuthCode(
            phone=phone,
            code_hash=_hash_code(phone, code),
            expires_at=now + timedelta(minutes=settings.auth_code_ttl_minutes),
        )
    )
    send_sms(phone, f"Код входа в СметаПро: {code}")


def _get_or_create_user(session: Session, phone: str) -> User:
    user = session.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(phone=phone)
        session.add(user)
    session.commit()
    return user


def verify_code(session: Session, phone: str, code: str) -> User:
    """Проверяет код; при успехе возвращает пользователя (создавая при первом входе)."""
    # Локальный стенд: универсальный dev-код (AUTH_DEV_CODE), чтобы входить
    # с телефона без чтения логов. На серверах переменная не задаётся.
    if settings.auth_dev_code and hmac.compare_digest(code, settings.auth_dev_code):
        return _get_or_create_user(session, phone)

    auth_code = session.scalar(
        select(AuthCode).where(AuthCode.phone == phone).order_by(AuthCode.id.desc()).limit(1)
    )
    now = datetime.now(timezone.utc)

    if (
        auth_code is None
        or auth_code.used_at is not None
        or auth_code.expires_at < now
        or auth_code.attempts >= MAX_VERIFY_ATTEMPTS
    ):
        raise InvalidCode

    if not hmac.compare_digest(auth_code.code_hash, _hash_code(phone, code)):
        auth_code.attempts += 1
        session.commit()
        raise InvalidCode

    auth_code.used_at = now
    return _get_or_create_user(session, phone)


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_ttl_days),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Возвращает user_id из токена; бросает jwt.InvalidTokenError, если токен плохой."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    return int(payload["sub"])

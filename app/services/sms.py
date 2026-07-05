"""Абстракция отправки SMS. Весь код проекта шлёт SMS только через send_sms().

Провайдер выбирается настройкой SMS_PROVIDER:
- stub — заглушка для разработки, пишет текст в лог (кода в БД нет, только хэш);
- реальный провайдер добавится сюда же отдельным классом, без правок остального кода.
"""
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class StubSmsProvider:
    """Заглушка: не отправляет ничего, пишет сообщение в лог."""

    def send(self, phone: str, text: str) -> None:
        logger.info("SMS-заглушка → %s: %s", phone, text)


def _get_provider():
    if settings.sms_provider == "stub":
        return StubSmsProvider()
    raise ValueError(f"Неизвестный SMS-провайдер: {settings.sms_provider}")


def send_sms(phone: str, text: str) -> None:
    _get_provider().send(phone, text)

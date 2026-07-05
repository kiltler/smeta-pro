"""Единственная точка доступа к файловому хранилищу (S3/MinIO).

Весь код приложения работает с файлами только через этот модуль —
смена провайдера хранилища не должна затрагивать остальной код.
"""
from minio import Minio

from app.config import settings

_client: Minio | None = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.s3_endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=settings.s3_secure,
        )
    return _client


def ensure_bucket() -> None:
    """Создаёт рабочий бакет, если его ещё нет (вызывается при старте приложения)."""
    client = get_client()
    if not client.bucket_exists(settings.s3_bucket):
        client.make_bucket(settings.s3_bucket)


def check_storage() -> None:
    """Проверка доступности хранилища (используется в /health). Бросает исключение при недоступности."""
    if not get_client().bucket_exists(settings.s3_bucket):
        raise RuntimeError(f"Бакет '{settings.s3_bucket}' не найден")

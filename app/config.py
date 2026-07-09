"""Настройки приложения: читаются из переменных окружения (.env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    secret_key: str = "dev-secret-change-me"

    database_url: str = "postgresql+psycopg://smeta:smeta@db:5432/smeta"

    s3_endpoint: str = "minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "smeta"
    s3_secure: bool = False

    # ИИ-парсер (Anthropic API)
    # Флаг выключен по умолчанию: без кредитов на аккаунте Anthropic
    # режимы «Голос»/«Текст» скрыты, работает режим «Шаблоны»
    parse_enabled: bool = False
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    # Биллинг (ЮKassa; тестовый магазин = тестовые shop_id/secret)
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    pro_price_rub: int = 790
    free_doc_limit: int = 3
    billing_grace_days: int = 3
    # Куда ЮKassa вернёт пользователя после оплаты
    billing_return_url: str = "http://localhost:5173/#/profile"

    # Вход по SMS-коду
    auth_code_ttl_minutes: int = 5
    auth_rate_limit_per_hour: int = 3
    jwt_ttl_days: int = 30
    sms_provider: str = "stub"
    sms_api_key: str = ""


settings = Settings()

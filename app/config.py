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

    # ИИ-парсер: false — выключен (только «Шаблоны»), mock — детерминированный
    # разбор по синонимам прайса без LLM (локальное тестирование),
    # true — реальный Anthropic API (нужны ключ и кредиты)
    parse_enabled: str = "false"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    # Мок-биллинг: кнопка оплаты сразу активирует Pro без ЮKassa
    # (локальное тестирование пейволла/лимитов/водяного знака). НЕ для серверов!
    mock_billing: bool = False

    # Универсальный код входа для локального стенда (пусто = выключен).
    # НИКОГДА не задавать на staging/prod!
    auth_dev_code: str = ""

    # Админка /admin (basic auth). Пусто = админка выключена (404)
    admin_user: str = ""
    admin_password: str = ""

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

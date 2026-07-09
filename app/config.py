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
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    # Вход по SMS-коду
    auth_code_ttl_minutes: int = 5
    auth_rate_limit_per_hour: int = 3
    jwt_ttl_days: int = 30
    sms_provider: str = "stub"
    sms_api_key: str = ""


settings = Settings()

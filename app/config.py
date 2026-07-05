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


settings = Settings()

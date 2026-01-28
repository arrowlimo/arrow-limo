from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Limo Backend (FastAPI)"
    environment: str = "development"
    log_level: str = "INFO"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "almsdata"
    db_user: str = "postgres"
    db_password: str  # Required via environment variable
    sentry_dsn: str | None = None
    cors_origins: list[str] = ["*"]

    # Pydantic v2 config
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Limo Backend (FastAPI)"
    environment: str = "production"
    log_level: str = "INFO"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "almsdata"
    db_user: str = "postgres"
    db_password: str | None = None
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.0
    cors_origins: list[str] = []
    trusted_hosts: list[str] = [
        "arrow-limo.onrender.com",
        "localhost",
        "127.0.0.1",
        "testserver",
    ]
    log_requests: bool = True
    security_headers_enabled: bool = True
    rate_limit_requests: int = 120
    auth_rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60
    max_login_attempts: int = 5
    login_lockout_minutes: int = 15
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None

    # Pydantic v2 config
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @field_validator("cors_origins", "trusted_hosts", mode="before")
    @classmethod
    def parse_list_env(cls, value: object) -> object:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    return [item.strip() for item in stripped.split(",") if item.strip()]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

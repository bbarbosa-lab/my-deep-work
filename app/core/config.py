from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "My Deep Work"
    environment: str = "development"
    debug: bool = True
    secret_key: str = "dev-secret-key-change-in-production-32chars-min"
    csrf_secret: str = "dev-csrf-secret-change-me"

    session_cookie_name: str = "mdw_session"
    session_ttl_seconds: int = 86400

    database_url: str = "postgresql://mdw:mdw_secret_change_me@db:5432/mydeepwork"
    redis_url: str = "redis://redis:6379/0"

    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_httponly: bool = True
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    rate_limit_login_ip: int = 10
    rate_limit_login_account: int = 5
    account_lockout_threshold: int = 5
    account_lockout_minutes: int = 15

    password_reset_ttl_seconds: int = 3600

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

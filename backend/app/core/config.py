from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://app:app@postgres:5432/app"
    redis_url: str = "redis://redis:6379/0"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    fernet_key: str

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"

    relevance_threshold: float = 0.6
    max_comments_per_hour: int = 10
    enable_automated_publishing: bool = False

    frontend_origin: str = "http://localhost:5173"

    admin_email: str = ""
    admin_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "职航智管"
    secret_key: str = "development-only-secret-change-before-deploy"
    access_token_expire_minutes: int = 120
    database_url: str = "sqlite:///./career.db"
    cors_origins: list[str] = ["http://localhost:5173"]
    storage_backend: str = "local"
    upload_dir: Path = Path("./uploads")
    max_upload_size_mb: int = 10
    agent_provider: str = "local"
    fastgpt_base_url: str = ""
    fastgpt_api_key: str = ""
    fastgpt_app_id: str = ""
    agent_timeout_seconds: int = 30
    enable_scheduler: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


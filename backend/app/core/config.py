import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "职航智管"
    secret_key: str = "development-only-secret-change-before-deploy"
    access_token_expire_minutes: int = 120
    database_url: str = "sqlite:///./career.db"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    storage_backend: str = "local"
    upload_dir: Path = Path("./uploads")
    max_upload_size_mb: int = 10
    agent_provider: str = "local"
    fastgpt_base_url: str = ""
    fastgpt_api_key: str = ""
    fastgpt_app_id: str = ""
    agent_timeout_seconds: int = 30
    enable_scheduler: bool = False
    demo_student_password: str = "Student123!"
    demo_counselor_password: str = "Counselor123!"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

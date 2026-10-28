import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_SECRETS_DIR = Path("/run/secrets")
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = Path(__file__).resolve().parents[3]
ENV_FILES = (PROJECT_DIR / ".env", BACKEND_DIR / ".env")


class Settings(BaseSettings):
    app_env: str = "development"
    deployment_mode: Literal["full", "server-demo"] = "full"
    app_name: str = "职航智管"
    secret_key: str = "development-only-secret-change-before-deploy"
    access_token_expire_minutes: int = 120
    database_url: str = "sqlite:///./career.db"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    storage_backend: str = "local"
    upload_dir: Path = Path("./uploads")
    storage_endpoint_url: str = ""
    storage_bucket: str = "career"
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_region: str = "us-east-1"
    storage_prefix: str = "career"
    storage_presigned_url_expiry: int = Field(default=900, ge=60, le=86_400)
    data_encryption_key: str = ""
    data_encryption_required: bool = False
    max_upload_size_mb: int = 10
    agent_provider: str = "local"
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_api_key: str = ""
    zhipu_model: str = "glm-4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-flash"
    agent_provider_order: str = "zhipu,deepseek"
    agent_allow_local_fallback: bool = False
    fastgpt_base_url: str = ""
    fastgpt_api_key: str = ""
    fastgpt_app_id: str = ""
    agent_timeout_seconds: int = 60
    agent_retry_attempts: int = 1
    agent_circuit_failure_threshold: int = 3
    agent_circuit_reset_seconds: int = 60
    agent_input_cost_per_million_usd: float | None = None
    agent_output_cost_per_million_usd: float | None = None
    metrics_enabled: bool = True
    rate_limit_enabled: bool = False
    rate_limit_backend: str = "memory"
    rate_limit_requests: int = Field(default=120, ge=1, le=100_000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3_600)
    redis_url: str = "redis://localhost:6379/0"
    otel_enabled: bool = False
    otel_service_name: str = "career-agent"
    otel_exporter_otlp_endpoint: str = ""
    agent_max_steps: int = Field(default=6, ge=1, le=12)
    agent_max_tool_calls: int = Field(default=12, ge=1, le=30)
    agent_max_tool_rounds: int = Field(default=2, ge=1, le=3)
    agent_max_parallel_reads: int = Field(default=3, ge=1, le=8)
    agent_run_timeout_seconds: int = Field(default=120, ge=10, le=600)
    chat_summary_message_threshold: int = Field(default=20, ge=4, le=200)
    chat_recent_message_limit: int = Field(default=12, ge=2, le=50)
    action_proposal_expiry_minutes: int = Field(default=30, ge=1, le=1_440)
    public_job_search_enabled: bool = True
    public_job_search_base_url: str = "https://cn.bing.com/search"
    public_job_search_timeout_seconds: int = Field(default=8, ge=1, le=30)
    public_job_search_max_results: int = Field(default=8, ge=1, le=20)
    public_job_search_retry_attempts: int = Field(default=1, ge=0, le=3)
    job_source_refresh_retry_attempts: int = Field(default=1, ge=0, le=3)
    embedding_service_url: str = "http://embedding:8101"
    ocr_service_url: str = "http://ocr:8102"
    speech_service_url: str = "http://speech:8103"
    emotion_service_url: str = "http://emotion:8104"
    emotion_analysis_timeout_seconds: int = Field(default=20, ge=3, le=120)
    ai_task_lease_seconds: int = 300
    ai_task_poll_seconds: float = 1.0
    audio_retention_days: int = 7
    audit_retention_days: int = Field(default=730, ge=30, le=3_650)
    agent_usage_retention_days: int = Field(default=90, ge=7, le=3_650)
    completed_task_retention_days: int = Field(default=30, ge=7, le=3_650)
    max_audio_size_mb: int = 20
    max_emotion_frame_size_mb: int = Field(default=4, ge=1, le=8)
    enable_scheduler: bool = False
    demo_student_password: str = "Student123!"
    demo_counselor_password: str = "Counselor123!"

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
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
    secrets_dir = DEFAULT_SECRETS_DIR if DEFAULT_SECRETS_DIR.is_dir() else None
    if secrets_dir is not None:
        return Settings(_env_file=None, _secrets_dir=secrets_dir)
    return Settings(_secrets_dir=None)

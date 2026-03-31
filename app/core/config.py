from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://jobqueue:jobqueue@localhost:5432/jobqueue"
    redis_url: str = "redis://localhost:6379/0"

    log_level: str = "INFO"
    worker_concurrency: int = 4
    job_max_execution_seconds: int = 300
    recovery_stuck_threshold_minutes: int = 10

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()

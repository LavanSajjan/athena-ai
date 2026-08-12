"""
Application settings.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.shared.constants import (
    APP_DESCRIPTION,
    APP_NAME,
    APP_VERSION,
    DEFAULT_STORAGE_ROOT,
    HOST,
    LOG_LEVEL,
    PORT,
)


class Settings(BaseSettings):
    """Athena configuration."""

    app_name: str = APP_NAME
    app_description: str = APP_DESCRIPTION
    app_version: str = APP_VERSION

    host: str = HOST
    port: int = PORT

    log_level: str = LOG_LEVEL

    storage_root: Path = Path(DEFAULT_STORAGE_ROOT)

    dataset_catalog_path: Path = Path("data/athena.sqlite3")

    dataset_query_memory_limit: str = "512MB"
    dataset_query_timeout_seconds: float = Field(default=30.0, gt=0)
    dataset_query_max_rows: int = Field(default=10_000, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

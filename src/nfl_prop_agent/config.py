"""Application configuration and environment loading utilities."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

try:  # pragma: no cover - fallback for limited environments
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - fallback for limited environments
    def load_dotenv(*args, **kwargs):
        logging.getLogger(__name__).warning(
            "python-dotenv is not installed; environment variables from .env will not be loaded."
        )
from pydantic import BaseSettings, Field, validator

load_dotenv()


class Settings(BaseSettings):
    """Configuration values read from environment variables."""

    data_directory: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "data",
        description="Directory containing bundled CSV data files.",
    )
    min_match_score: int = Field(85, ge=0, le=100, description="Minimum RapidFuzz score to consider a player match valid.")
    logistic_slope: float = Field(
        0.08,
        gt=0.0,
        description="Slope parameter for logistic projection probability conversion.",
    )
    http_timeout: float = Field(5.0, gt=0.0, description="Timeout in seconds for outbound HTTP requests.")
    log_level: str = Field("INFO", description="Python logging level for the application.")

    class Config:
        env_prefix = "NFL_PROP_"
        case_sensitive = False

    @validator("data_directory")
    def _ensure_data_directory(cls, value: Path) -> Path:
        if not value.exists():
            logging.getLogger(__name__).warning("Data directory %s does not exist; creating it.", value)
            value.mkdir(parents=True, exist_ok=True)
        return value


@lru_cache()
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""

    return Settings()  # type: ignore[call-arg]


settings: Settings = get_settings()

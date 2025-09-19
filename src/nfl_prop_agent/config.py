"""Application configuration and environment loading utilities (Pydantic v2)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

# Load .env if present (non-fatal if missing)
load_dotenv(dotenv_path=Path(".env"), override=False)

MA_BOOKS_DEFAULT = [
    "DraftKings",
    "FanDuel",
    "BetMGM",
    "Caesars",
    "ESPN BET",
    "Fanatics",
    "Bally Bet",
]

MARKETS_DEFAULT = [
    "player_pass_yds",
    "player_pass_tds",
    "player_pass_interceptions",
    "player_rush_yds",
    "player_rush_tds",
    "player_receptions",
    "player_reception_yds",
    "player_reception_tds",
    "player_goal_scorer_anytime",
]


class Settings(BaseSettings):
    """Runtime settings loaded from env with sane defaults (Pydantic v2)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # API / external
    ODDS_API_KEY: Optional[str] = Field(default=None, description="The Odds API key")

    # Filters
    MA_BOOKS: list[str] = Field(default_factory=lambda: MA_BOOKS_DEFAULT.copy())
    MARKETS: list[str] = Field(default_factory=lambda: MARKETS_DEFAULT.copy())

    # Guardrails
    ODDS_MIN: int = Field(default=-200)      # ignore shorter than -200
    ODDS_MAX: int = Field(default=500)       # ignore longer than +500
    MIN_BOOKS: int = Field(default=3)
    MAX_VIG: float = Field(default=0.06)

    # Thresholds
    SHORTLIST_EV: float = Field(default=0.03)
    RECOMMEND_EV: float = Field(default=0.05)
    Z_YARDS: float = Field(default=0.40)
    Z_YARDS_STRONG: float = Field(default=0.65)
    Z_REC: float = Field(default=0.55)
    Z_REC_STRONG: float = Field(default=0.80)

    # Bankroll
    BANKROLL_UNITS: float = Field(default=100.0)
    KELLY_MULTIPLIER: float = Field(default=0.5)

    # IO
    OUT_DIR: Path = Field(default_factory=lambda: Path("out"))
    DATA_DIR: Path = Field(default_factory=lambda: Path("data"))

    # Slack
    SLACK_WEBHOOK_URL: Optional[str] = Field(default=None)

    @field_validator("OUT_DIR", "DATA_DIR", mode="before")
    @classmethod
    def _ensure_path(cls, v: str | Path) -> Path:
        p = Path(v)
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception as exc:  # pragma: no cover
                log.warning("Could not create directory %s: %s", p, exc)
        return p

    @computed_field  # type: ignore[misc]
    @property
    def MA_BOOKS_SET(self) -> set[str]:
        return {b.lower() for b in self.MA_BOOKS}


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()

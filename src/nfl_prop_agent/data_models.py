"""Typed data models representing player props and projections."""

from __future__ import annotations

from pydantic import BaseModel, Field, validator


class PlayerProp(BaseModel):
    """Representation of a sportsbook player prop market."""

    player: str = Field(..., description="Player full name as listed by the book.")
    team: str = Field(..., description="Team abbreviation.")
    market: str = Field(..., description="Prop market, e.g. passing_yards.")
    line: float = Field(..., description="Posted prop line.")
    odds: int = Field(..., description="American odds for the over bet.")
    sportsbook: str = Field(..., description="Sportsbook offering the market.")

    @validator("player", "team", "market", "sportsbook")
    def _strip_strings(cls, value: str) -> str:
        return value.strip()


class Projection(BaseModel):
    """Representation of a model projection for a player market."""

    player: str = Field(..., description="Player full name from the projection model.")
    team: str = Field(..., description="Team abbreviation.")
    market: str = Field(..., description="Prop market name.")
    projection: float = Field(..., description="Projected stat outcome for the market.")
    source: str = Field(..., description="Projection source identifier.")

    @validator("player", "team", "market", "source")
    def _strip_strings(cls, value: str) -> str:
        return value.strip()


class EdgeResult(BaseModel):
    """Calculated value edge for a specific player prop."""

    player: str
    matched_player: str
    match_score: float
    team: str
    market: str
    sportsbook: str
    line: float
    odds: int
    projection: float
    projected_probability: float
    implied_probability: float
    edge: float
    source: str

    class Config:
        frozen = True

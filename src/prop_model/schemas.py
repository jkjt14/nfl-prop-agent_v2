"""Pydantic schemas describing normalized prop model data."""

from __future__ import annotations

from pydantic import BaseModel, Field, validator


class ProjectionRow(BaseModel):
    """Representation of a single projection record produced upstream."""

    player: str = Field(..., description="Normalized player name.")
    team: str = Field(..., description="Team abbreviation.")
    position: str = Field(..., description="Player position code.")
    id: str = Field(..., description="Source-specific player identifier.")
    season_year: int = Field(..., description="Season year for the projection.")
    week: int = Field(..., description="Week number associated with the projection.")
    avg_type: str = Field(..., description="Averaging methodology label (mean, median, etc.).")
    pass_yds: float = Field(..., description="Projected passing yards.")
    pass_yds_sd: float = Field(
        ..., ge=0.0, description="Standard deviation for projected passing yards."
    )
    pass_tds: float = Field(..., description="Projected passing touchdowns.")
    pass_tds_sd: float = Field(
        ..., ge=0.0, description="Standard deviation for projected passing touchdowns."
    )
    pass_int: float = Field(..., description="Projected interceptions thrown.")
    pass_int_sd: float = Field(
        ..., ge=0.0, description="Standard deviation for projected interceptions thrown."
    )
    rush_yds: float = Field(..., description="Projected rushing yards.")
    rush_yds_sd: float = Field(
        ..., ge=0.0, description="Standard deviation for projected rushing yards."
    )
    rush_tds: float = Field(..., description="Projected rushing touchdowns.")
    rush_tds_sd: float = Field(
        ..., ge=0.0, description="Standard deviation for projected rushing touchdowns."
    )
    rec: float = Field(..., description="Projected receptions.")
    rec_sd: float = Field(
        ..., ge=0.0, description="Standard deviation for projected receptions."
    )
    rec_yds: float = Field(..., description="Projected receiving yards.")
    rec_yds_sd: float = Field(
        ..., ge=0.0, description="Standard deviation for projected receiving yards."
    )
    rec_tds: float = Field(..., description="Projected receiving touchdowns.")
    rec_tds_sd: float = Field(
        ..., ge=0.0, description="Standard deviation for projected receiving touchdowns."
    )
    injury_status: str = Field(
        "OK", description="Injury designation code used for downstream filtering."
    )

    @validator(
        "player",
        "team",
        "position",
        "id",
        "avg_type",
        "injury_status",
    )
    def _strip_strings(cls, value: str) -> str:
        """Trim whitespace from string-based fields."""

        return value.strip()


class OddsRow(BaseModel):
    """Normalized sportsbook odds record."""

    event_id: str = Field(..., description="Unique event identifier from the sportsbook.")
    event_start: str = Field(..., description="Scheduled start time for the event.")
    player: str = Field(..., description="Player name listed by the sportsbook.")
    team: str = Field(..., description="Team abbreviation from the sportsbook line.")
    market: str = Field(..., description="Prop market identifier.")
    side: str = Field(..., description="Side of the market, e.g. over or under.")
    line: float = Field(..., description="Posted market line value.")
    price_american: int = Field(..., description="American odds for the listed side.")
    bookmaker_title: str = Field(..., description="Bookmaker or sportsbook title.")
    last_update: str = Field(..., description="Timestamp of the line's most recent update.")

    @validator(
        "event_id",
        "event_start",
        "player",
        "team",
        "market",
        "side",
        "bookmaker_title",
        "last_update",
    )
    def _strip_strings(cls, value: str) -> str:
        """Trim whitespace from string-based fields."""

        return value.strip()


class JoinedPropRow(BaseModel):
    """Combined projection and odds record with derived metrics."""

    player: str = Field(..., description="Player name for the joined prop record.")
    team: str = Field(..., description="Team abbreviation.")
    position: str = Field(..., description="Player position.")
    market: str = Field(..., description="Prop market identifier.")
    side: str = Field(..., description="Side of the market (over/under/etc.).")
    line: float = Field(..., description="Market line sourced from the sportsbook.")
    proj_mean: float = Field(..., description="Mean projection for the given stat.")
    proj_sd: float = Field(
        ..., ge=0.0, description="Standard deviation around the projection."
    )
    price_american: int = Field(..., description="American odds posted by the book.")
    implied_prob: float = Field(
        ..., ge=0.0, le=1.0, description="Implied probability derived from the odds."
    )
    prob_model: float = Field(
        ..., ge=0.0, le=1.0, description="Model-estimated probability of the side hitting."
    )
    ev_per_dollar: float = Field(
        ..., description="Expected value per dollar wagered on the market."
    )
    z_score: float = Field(
        ..., description="Standardized difference between projection and sportsbook line."
    )
    kelly_fraction: float = Field(
        ..., ge=0.0, description="Recommended Kelly stake fraction for the market."
    )
    unit_size: float = Field(
        ..., ge=0.0, description="Recommended staking units based on bankroll settings."
    )
    bookmaker_title: str = Field(..., description="Bookmaker or sportsbook title.")
    event_id: str = Field(..., description="Associated sportsbook event identifier.")
    event_start: str = Field(..., description="Event start time for the matchup.")
    tier: str = Field(..., description="Recommendation tier derived from thresholds.")

    @validator(
        "player",
        "team",
        "position",
        "market",
        "side",
        "bookmaker_title",
        "event_id",
        "event_start",
        "tier",
    )
    def _strip_strings(cls, value: str) -> str:
        """Trim whitespace from string-based fields."""

        return value.strip()

"""Core logic for matching props to projections and computing edges."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import pandas as pd
from rapidfuzz import fuzz, process

from .config import get_settings
from .data_models import EdgeResult, PlayerProp, Projection
from .exceptions import MatchNotFoundError
from .logging_utils import configure_logging

LOGGER = configure_logging(__name__)


def american_to_implied_prob(odds: int) -> float:
    """Convert American odds to implied probability."""

    if odds == 0:
        raise ValueError("American odds cannot be zero.")
    if odds > 0:
        prob = 100 / (odds + 100)
    else:
        prob = -odds / (-odds + 100)
    LOGGER.debug("Converted odds %s to implied probability %.4f", odds, prob)
    return prob


def logistic_probability(line: float, projection: float, slope: float | None = None) -> float:
    """Approximate the over hit probability using a logistic transform."""

    slope_value = slope if slope is not None else get_settings().logistic_slope
    diff = projection - line
    prob = 1.0 / (1.0 + math.exp(-slope_value * diff))
    LOGGER.debug(
        "Computed logistic probability with slope %.4f (diff %.2f): %.4f",
        slope_value,
        diff,
        prob,
    )
    return prob


@dataclass(frozen=True)
class MatchedProjection:
    """Container linking a prop to the best projection match."""

    projection: Projection
    score: float


class EdgeCalculator:
    """Calculate value edges for sportsbook player props."""

    def __init__(self, projections: Sequence[Projection], min_match_score: int | None = None) -> None:
        self._projections = list(projections)
        if not self._projections:
            raise ValueError("At least one projection is required to build EdgeCalculator.")
        settings = get_settings()
        self._min_match_score = (
            min_match_score if min_match_score is not None else settings.min_match_score
        )
        LOGGER.info(
            "EdgeCalculator initialized with %d projections and min_match_score=%d",
            len(self._projections),
            self._min_match_score,
        )

    def _eligible_projections(self, market: str) -> List[Projection]:
        return [projection for projection in self._projections if projection.market.lower() == market.lower()]

    def match_prop(self, prop: PlayerProp) -> MatchedProjection:
        """Return the best projection for the given prop."""

        eligible = self._eligible_projections(prop.market)
        if not eligible:
            raise MatchNotFoundError(f"No projections available for market {prop.market}")

        names = [projection.player for projection in eligible]
        best_match = process.extractOne(
            prop.player,
            names,
            scorer=fuzz.WRatio,
        )
        if best_match is None:
            raise MatchNotFoundError(f"No projection matched for {prop.player}")
        _, score, index = best_match
        if score < self._min_match_score:
            raise MatchNotFoundError(
                f"Best match score {score:.1f} for {prop.player} below threshold {self._min_match_score}"
            )
        projection = eligible[index]
        LOGGER.debug(
            "Matched prop '%s' to projection '%s' with score %.1f",
            prop.player,
            projection.player,
            score,
        )
        return MatchedProjection(projection=projection, score=score)

    @staticmethod
    def build_edge(prop: PlayerProp, matched: MatchedProjection) -> EdgeResult:
        """Calculate the betting edge for a single prop using its matched projection."""

        implied_prob = american_to_implied_prob(prop.odds)
        projected_prob = logistic_probability(prop.line, matched.projection.projection)
        edge_value = projected_prob - implied_prob
        return EdgeResult(
            player=prop.player,
            matched_player=matched.projection.player,
            match_score=matched.score,
            team=prop.team,
            market=prop.market,
            sportsbook=prop.sportsbook,
            line=prop.line,
            odds=prop.odds,
            projection=matched.projection.projection,
            projected_probability=projected_prob,
            implied_probability=implied_prob,
            edge=edge_value,
            source=matched.projection.source,
        )

    def calculate_edges(self, props: Iterable[PlayerProp]) -> pd.DataFrame:
        """Calculate edges for a sequence of props, returning a tidy DataFrame."""

        results: List[EdgeResult] = []
        for prop in props:
            try:
                matched = self.match_prop(prop)
            except MatchNotFoundError as exc:
                LOGGER.warning("Skipping prop for %s: %s", prop.player, exc)
                continue
            result = self.build_edge(prop, matched)
            results.append(result)
        if not results:
            raise MatchNotFoundError("No props could be matched to projections.")
        df = pd.DataFrame([result.dict() for result in results])
        df.sort_values(by="edge", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)
        LOGGER.info("Calculated edges for %d props", len(df))
        return df

"""Unit tests for edge calculation logic."""

from __future__ import annotations

import math

import pytest

from nfl_prop_agent.data_models import PlayerProp, Projection
from nfl_prop_agent.edge_calculator import EdgeCalculator, american_to_implied_prob, logistic_probability


@pytest.fixture()
def sample_props() -> list[PlayerProp]:
    return [
        PlayerProp(
            player="Patrick Mahomes II",
            team="KC",
            market="passing_yards",
            line=285.5,
            odds=-110,
            sportsbook="DraftKings",
        ),
        PlayerProp(
            player="Josh Allen",
            team="BUF",
            market="passing_yards",
            line=270.5,
            odds=-105,
            sportsbook="FanDuel",
        ),
    ]


@pytest.fixture()
def sample_projections() -> list[Projection]:
    return [
        Projection(
            player="Patrick Mahomes",
            team="KC",
            market="passing_yards",
            projection=301.2,
            source="Model A",
        ),
        Projection(
            player="Josh Allen",
            team="BUF",
            market="passing_yards",
            projection=283.4,
            source="Model A",
        ),
    ]


def test_american_odds_conversion() -> None:
    assert math.isclose(american_to_implied_prob(-110), 110 / 210, rel_tol=1e-6)
    assert math.isclose(american_to_implied_prob(130), 100 / 230, rel_tol=1e-6)


def test_logistic_probability_is_half_when_equal() -> None:
    assert math.isclose(logistic_probability(100.0, 100.0, slope=0.5), 0.5, rel_tol=1e-6)


def test_calculate_edges_orders_by_value(sample_props: list[PlayerProp], sample_projections: list[Projection]) -> None:
    calculator = EdgeCalculator(sample_projections, min_match_score=70)
    report = calculator.calculate_edges(sample_props)
    assert list(report.columns) == [
        "player",
        "matched_player",
        "match_score",
        "team",
        "market",
        "sportsbook",
        "line",
        "odds",
        "projection",
        "projected_probability",
        "implied_probability",
        "edge",
        "source",
    ]
    assert report.iloc[0]["player"] == "Patrick Mahomes II"
    assert report.iloc[0]["edge"] >= report.iloc[1]["edge"]


def test_high_threshold_filters(sample_props: list[PlayerProp], sample_projections: list[Projection]) -> None:
    calculator = EdgeCalculator(sample_projections, min_match_score=99)
    report = calculator.calculate_edges(sample_props)
    assert len(report) == 1
    assert report.iloc[0]["player"] == "Josh Allen"

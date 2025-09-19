"""Tests for prop model data schemas."""

from __future__ import annotations

import pytest

from prop_model.schemas import JoinedPropRow, OddsRow, ProjectionRow


def _projection_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "player": " Patrick Mahomes ",
        "team": " KC ",
        "position": " QB ",
        "id": " qb-15 ",
        "season_year": "2024",
        "week": "1",
        "avg_type": " mean ",
        "pass_yds": "305.5",
        "pass_yds_sd": "12.0",
        "pass_tds": "2.4",
        "pass_tds_sd": "0.8",
        "pass_int": "0.7",
        "pass_int_sd": "0.2",
        "rush_yds": "25.5",
        "rush_yds_sd": "5.0",
        "rush_tds": "0.3",
        "rush_tds_sd": "0.1",
        "rec": "0.0",
        "rec_sd": "0.0",
        "rec_yds": "0.0",
        "rec_yds_sd": "0.0",
        "rec_tds": "0.0",
        "rec_tds_sd": "0.0",
    }
    base.update(overrides)
    return base


def _odds_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "event_id": " evt-1 ",
        "event_start": " 2024-09-08T13:00:00Z ",
        "player": " Patrick Mahomes ",
        "team": " KC ",
        "market": " player_pass_yds ",
        "side": " over ",
        "line": "305.5",
        "price_american": "-110",
        "bookmaker_title": " DraftKings ",
        "last_update": " 2024-09-08T12:30:00Z ",
    }
    base.update(overrides)
    return base


def _joined_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "player": " Patrick Mahomes ",
        "team": " KC ",
        "position": " QB ",
        "market": " player_pass_yds ",
        "side": " over ",
        "line": "305.5",
        "proj_mean": "306.8",
        "proj_sd": "11.5",
        "price_american": "-110",
        "implied_prob": "0.52",
        "prob_model": "0.57",
        "ev_per_dollar": "0.05",
        "z_score": "0.11",
        "kelly_fraction": "0.06",
        "unit_size": "1.2",
        "bookmaker_title": " DraftKings ",
        "event_id": " evt-1 ",
        "event_start": " 2024-09-08T13:00:00Z ",
        "tier": " shortlist ",
    }
    base.update(overrides)
    return base


def test_projection_row_casts_and_trims() -> None:
    row = ProjectionRow(**_projection_payload())
    assert row.player == "Patrick Mahomes"
    assert row.team == "KC"
    assert row.season_year == 2024
    assert row.week == 1
    assert row.pass_yds == pytest.approx(305.5, rel=1e-9)
    assert row.pass_yds_sd == pytest.approx(12.0)
    assert row.injury_status == "OK"


def test_projection_row_rejects_negative_deviation() -> None:
    with pytest.raises(ValueError):
        ProjectionRow(**_projection_payload(pass_yds_sd=-1))


def test_odds_row_casts_numeric_fields() -> None:
    row = OddsRow(**_odds_payload())
    assert row.line == pytest.approx(305.5)
    assert row.price_american == -110
    assert row.bookmaker_title == "DraftKings"


def test_joined_row_enforces_probability_bounds() -> None:
    row = JoinedPropRow(**_joined_payload())
    assert row.proj_sd == pytest.approx(11.5)
    assert row.implied_prob == pytest.approx(0.52)
    assert row.prob_model == pytest.approx(0.57)
    assert row.tier == "shortlist"


def test_joined_row_rejects_probability_above_one() -> None:
    with pytest.raises(ValueError):
        JoinedPropRow(**_joined_payload(implied_prob=1.2))

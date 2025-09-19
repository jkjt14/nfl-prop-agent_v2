"""Core joining and edge calculation logic for the prop model."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from . import config
from . import mapping


_OUTPUT_COLUMNS = [
    "player",
    "team",
    "position",
    "market",
    "side",
    "line",
    "proj_mean",
    "proj_sd",
    "price_american",
    "implied_prob",
    "prob_model",
    "ev_per_dollar",
    "z_score",
    "kelly_fraction",
    "unit_size",
    "bookmaker_title",
    "event_id",
    "event_start",
    "tier",
]

_BASE_MARKET_TO_PROJECTION = {
    "pass_yds": ("pass_yds", "pass_yds_sd"),
    "pass_tds": ("pass_tds", "pass_tds_sd"),
    "pass_int": ("pass_int", "pass_int_sd"),
    "rush_yds": ("rush_yds", "rush_yds_sd"),
    "rush_tds": ("rush_tds", "rush_tds_sd"),
    "receptions": ("rec", "rec_sd"),
    "reception_yds": ("rec_yds", "rec_yds_sd"),
    "reception_tds": ("rec_tds", "rec_tds_sd"),
}

_YARD_MARKETS = {"pass_yds", "rush_yds", "reception_yds"}


def american_to_prob(odds: int | float) -> float:
    """Convert American odds to implied probability."""

    if odds is None:
        raise ValueError("American odds value is required for conversion")

    value = float(odds)
    if math.isnan(value) or value == 0.0:
        raise ValueError("American odds must be a non-zero numeric value")

    if value > 0:
        return 100.0 / (value + 100.0)
    return -value / (-value + 100.0)


def prob_to_american(probability: float) -> int:
    """Convert a win probability to the equivalent American odds."""

    if probability <= 0.0 or probability >= 1.0:
        raise ValueError("Probability must be strictly between 0 and 1")

    if probability > 0.5:
        odds = -100.0 * probability / (1.0 - probability)
    elif probability < 0.5:
        odds = 100.0 * (1.0 - probability) / probability
    else:
        odds = -100.0
    return int(round(odds))


def _normal_cdf(value: float) -> float:
    """Fast approximation of the standard normal CDF using math.erf."""

    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def prob_over(line: float, mean: float, sd: float) -> float:
    """Probability of exceeding the betting line given a normal projection."""

    if sd is None or math.isnan(sd) or sd <= 0.0:
        if math.isnan(mean) or math.isnan(line):
            return float("nan")
        if mean > line:
            return 1.0
        if mean < line:
            return 0.0
        return 0.5

    z = (line - mean) / sd
    return 1.0 - _normal_cdf(z)


def prob_under(line: float, mean: float, sd: float) -> float:
    """Probability of falling short of the betting line."""

    if sd is None or math.isnan(sd) or sd <= 0.0:
        if math.isnan(mean) or math.isnan(line):
            return float("nan")
        if mean < line:
            return 1.0
        if mean > line:
            return 0.0
        return 0.5

    z = (line - mean) / sd
    return _normal_cdf(z)


def market_hold_from_best(over_price: int | float | None, under_price: int | float | None) -> float:
    """Calculate market hold using the best over and under prices."""

    if over_price is None or under_price is None:
        return float("inf")
    try:
        over_prob = american_to_prob(over_price)
        under_prob = american_to_prob(under_price)
    except ValueError:
        return float("inf")

    hold = over_prob + under_prob - 1.0
    return max(hold, 0.0)


def _normalize_market_key(market: str) -> str:
    key = (market or "").strip().lower().replace(" ", "_")
    if key.startswith("player_"):
        key = key[len("player_") :]
    if key == "pass_interceptions":
        key = "pass_int"
    return key


def _clean_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _coalesce_norm(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return ""


def _projection_columns(market_key: str) -> tuple[str, str] | None:
    return _BASE_MARKET_TO_PROJECTION.get(market_key)


def _is_yard_market(market_key: str) -> bool:
    return market_key in _YARD_MARKETS


def _book_counts(odds_df: pd.DataFrame) -> dict[tuple[str, str, str], int]:
    grouped = odds_df.groupby(["player_norm", "team_norm", "market_key"])["bookmaker_title"].nunique()
    return grouped.to_dict()


def _market_vig(odds_df: pd.DataFrame) -> dict[tuple[str, str, str], float]:
    if odds_df.empty:
        return {}

    df = odds_df.copy()
    df["side_norm"] = df["side"].str.lower()
    df = df[df["side_norm"].isin(["over", "under"])]
    if df.empty:
        return {}

    df["implied_prob"] = df["price_american"].apply(lambda value: american_to_prob(int(value)))

    group_keys = ["player_norm", "team_norm", "market_key"]
    over_probs = df[df["side_norm"] == "over"].groupby(group_keys)["implied_prob"].min()
    under_probs = df[df["side_norm"] == "under"].groupby(group_keys)["implied_prob"].min()

    vig: dict[tuple[str, str, str], float] = {}
    keys: set[tuple[str, str, str]] = set(over_probs.index) | set(under_probs.index)
    for key in keys:
        over_prob = over_probs.get(key)
        under_prob = under_probs.get(key)
        if over_prob is None or under_prob is None or math.isnan(over_prob) or math.isnan(under_prob):
            vig[key] = float("inf")
            continue
        hold = over_prob + under_prob - 1.0
        vig[key] = max(hold, 0.0)
    return vig


def _kelly_fraction(prob_win: float, odds: int) -> float:
    payout = odds / 100.0 if odds > 0 else 100.0 / abs(odds)
    if payout <= 0:
        return 0.0
    loss_prob = 1.0 - prob_win
    fraction = (payout * prob_win - loss_prob) / payout
    return max(fraction, 0.0)


def _prepare_projection_frame(proj_df: pd.DataFrame) -> pd.DataFrame:
    if proj_df.empty:
        return proj_df.copy()
    projections = proj_df.copy()
    if "injury_status" not in projections.columns:
        projections["injury_status"] = "OK"
    projections = projections.reset_index(drop=True)
    projections["proj_index"] = projections.index
    projections = mapping.canonicalize(projections)
    return projections


def _prepare_odds_frame(odds_df: pd.DataFrame, proj_positions: pd.DataFrame) -> pd.DataFrame:
    if odds_df.empty:
        return odds_df.copy()

    odds = odds_df.copy()
    odds = odds.reset_index(drop=True)
    odds["odds_index"] = odds.index

    for column in ("side", "market", "bookmaker_title", "event_id", "event_start", "player", "team"):
        if column in odds.columns:
            odds[column] = odds[column].astype(str).str.strip()

    if "position" not in odds.columns:
        odds["position"] = ""

    odds["side"] = odds["side"].str.lower()
    odds = odds[odds["side"].isin(["over", "under"])]

    odds["price_american"] = pd.to_numeric(odds.get("price_american"), errors="coerce")
    odds["line"] = pd.to_numeric(odds.get("line"), errors="coerce")
    odds = odds.dropna(subset=["price_american", "line", "market", "player", "team"])

    odds["price_american"] = odds["price_american"].astype(int)

    odds = odds[
        (odds["price_american"] >= config.ODDS_MIN)
        & (odds["price_american"] <= config.ODDS_MAX)
    ]

    odds = odds[~odds["bookmaker_title"].str.contains("boost", case=False, na=False)]

    odds["market_key"] = odds["market"].apply(_normalize_market_key)
    odds = odds[odds["market_key"].isin(_BASE_MARKET_TO_PROJECTION)]

    canonical = mapping.canonicalize(odds)
    if not proj_positions.empty:
        canonical = canonical.merge(
            proj_positions,
            on=["player_norm", "team_norm"],
            how="left",
            suffixes=("", "_proj"),
        )
        missing = canonical["pos_norm"].eq("") | canonical["pos_norm"].isna()
        canonical.loc[missing, "pos_norm"] = canonical.loc[missing, "pos_norm_proj"].fillna("")
        canonical.loc[missing, "position"] = canonical.loc[missing, "position_proj"].fillna("")
        canonical = canonical.drop(columns=["pos_norm_proj", "position_proj"], errors="ignore")

    return canonical


def _build_position_lookup(projections: pd.DataFrame) -> pd.DataFrame:
    if projections.empty:
        return pd.DataFrame(columns=["player_norm", "team_norm", "position", "pos_norm"])
    lookup = projections[["player_norm", "team_norm", "position", "pos_norm"]].drop_duplicates(
        subset=["player_norm", "team_norm"]
    )
    return lookup


def _combine_exact_matches(
    odds: pd.DataFrame, projections: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if odds.empty:
        return pd.DataFrame(), pd.DataFrame()

    merged = odds.merge(
        projections,
        on=["player_norm", "team_norm", "pos_norm"],
        how="left",
        suffixes=("_odds", "_proj"),
    )
    matched = merged[merged["proj_index"].notna()].copy()
    unmatched_odds = odds.loc[~odds["odds_index"].isin(matched["odds_index"])]
    return matched, unmatched_odds


def _combine_fuzzy_matches(
    unmatched_odds: pd.DataFrame,
    raw_odds: pd.DataFrame,
    projections: pd.DataFrame,
) -> pd.DataFrame:
    if unmatched_odds.empty:
        return pd.DataFrame()

    unmatched_indices = set(unmatched_odds["odds_index"].tolist())
    odds_subset = raw_odds[raw_odds["odds_index"].isin(unmatched_indices)]
    fuzzy = mapping.fuzzy_join(odds_subset, projections)
    if fuzzy.empty:
        return pd.DataFrame()

    index_map = {
        int(row["left_odds_index"]): int(row["right_proj_index"])
        for _, row in fuzzy.iterrows()
        if not pd.isna(row["right_proj_index"])
    }
    if not index_map:
        return pd.DataFrame()

    subset = unmatched_odds[unmatched_odds["odds_index"].isin(index_map)].copy()
    subset["proj_index"] = subset["odds_index"].map(index_map)
    joined = subset.merge(
        projections,
        on="proj_index",
        how="left",
        suffixes=("_odds", "_proj"),
    )
    return joined


def _tier_for_market(ev: float, z_score: float, market_key: str) -> str:
    abs_z = abs(z_score)
    if _is_yard_market(market_key):
        strong = config.Z_YARDS_STRONG
        moderate = config.Z_YARDS
    else:
        strong = config.Z_REC_STRONG
        moderate = config.Z_REC

    if ev >= config.RECOMMEND_EV and abs_z >= strong:
        return "RECOMMEND"
    if ev >= config.SHORTLIST_EV and abs_z >= moderate:
        return "SHORTLIST"
    return "PASS"


def _finalize_units(kelly_fraction: float) -> float:
    if kelly_fraction <= 0.0:
        return 0.0
    units = kelly_fraction * config.BANKROLL_UNITS
    return float(min(max(units, 0.2), 1.5))


def join_and_score(proj_df: pd.DataFrame, odds_df: pd.DataFrame) -> pd.DataFrame:
    """Join projections with sportsbook odds and compute betting edges."""

    if proj_df.empty or odds_df.empty:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)

    projections = _prepare_projection_frame(proj_df)
    if projections.empty:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)

    position_lookup = _build_position_lookup(projections)
    odds_canonical = _prepare_odds_frame(odds_df, position_lookup)
    if odds_canonical.empty:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)

    odds_raw = odds_df.copy()
    if "position" not in odds_raw.columns:
        odds_raw["position"] = ""
    odds_raw = odds_raw.reset_index(drop=True)
    odds_raw["odds_index"] = odds_raw.index
    odds_raw.loc[odds_canonical.index, "position"] = odds_canonical["position"].values

    matched_exact, unmatched_odds = _combine_exact_matches(odds_canonical, projections)
    matched_fuzzy = _combine_fuzzy_matches(unmatched_odds, odds_raw, projections)

    combined = pd.concat([matched_exact, matched_fuzzy], ignore_index=True, sort=False)
    if combined.empty:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)

    books = _book_counts(odds_canonical)
    vigs = _market_vig(odds_canonical)

    records: list[dict[str, Any]] = []
    for _, row in combined.iterrows():
        market_key = row.get("market_key")
        if not market_key:
            continue
        proj_cols = _projection_columns(str(market_key))
        if not proj_cols:
            continue

        proj_mean = row.get(proj_cols[0])
        proj_sd = row.get(proj_cols[1])
        line = row.get("line")
        price = row.get("price_american")
        side = str(row.get("side", "")).strip().lower()
        if side not in {"over", "under"}:
            continue
        if any(pd.isna(value) for value in (proj_mean, proj_sd, line, price)):
            continue

        player_norm = _coalesce_norm(row.get("player_norm_odds"), row.get("player_norm_proj"))
        team_norm = _coalesce_norm(row.get("team_norm_odds"), row.get("team_norm_proj"))
        if not player_norm or not team_norm:
            continue

        key = (player_norm, team_norm, market_key)

        book_count = books.get(key, 0)
        if book_count < config.MIN_BOOKS:
            continue

        vig = vigs.get(key, float("inf"))
        if not math.isfinite(vig) or vig > config.MAX_VIG:
            continue

        try:
            implied_prob = american_to_prob(int(price))
        except ValueError:
            continue

        mean_value = float(proj_mean)
        sd_value = float(proj_sd)
        line_value = float(line)
        price_value = int(price)

        if side == "over":
            prob_model = prob_over(line_value, mean_value, sd_value)
            z_score = (mean_value - line_value) / sd_value if sd_value > 0 else 0.0
        else:
            prob_model = prob_under(line_value, mean_value, sd_value)
            z_raw = (mean_value - line_value) / sd_value if sd_value > 0 else 0.0
            z_score = -z_raw

        if math.isnan(prob_model):
            continue
        prob_model = max(0.0, min(1.0, prob_model))

        payout = price_value / 100.0 if price_value > 0 else 100.0 / abs(price_value)
        ev_per_dollar = prob_model * payout - (1.0 - prob_model)

        kelly_base = _kelly_fraction(prob_model, price_value)
        kelly_fraction = kelly_base * config.KELLY_MULTIPLIER
        injury_status = str(row.get("injury_status", "")).upper()
        if injury_status in config.INJURY_DROP_STATUSES:
            continue
        unit_size = _finalize_units(kelly_fraction)
        if injury_status in config.INJURY_HALF_STATUSES:
            kelly_fraction *= 0.5
            unit_size *= 0.5
        kelly_fraction = max(kelly_fraction, 0.0)
        unit_size = max(unit_size, 0.0)

        tier = _tier_for_market(ev_per_dollar, z_score, str(market_key))

        record: dict[str, Any] = {
            "player": _clean_string(row.get("player_odds") or row.get("player_proj")),
            "team": _clean_string(row.get("team_odds") or row.get("team_proj")),
            "position": _clean_string(row.get("position_proj") or row.get("position_odds")),
            "market": _clean_string(row.get("market")),
            "side": side,
            "line": float(line_value),
            "proj_mean": float(mean_value),
            "proj_sd": float(sd_value),
            "price_american": int(price_value),
            "implied_prob": float(implied_prob),
            "prob_model": float(prob_model),
            "ev_per_dollar": float(ev_per_dollar),
            "z_score": float(z_score),
            "kelly_fraction": float(kelly_fraction),
            "unit_size": float(unit_size),
            "bookmaker_title": _clean_string(row.get("bookmaker_title")),
            "event_id": _clean_string(row.get("event_id")),
            "event_start": _clean_string(row.get("event_start")),
            "tier": tier,
        }

        if record["unit_size"] > 0:
            record["unit_size"] = float(min(max(record["unit_size"], 0.2), 1.5))

        records.append(record)

    if not records:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)

    result = pd.DataFrame(records)
    result = result[_OUTPUT_COLUMNS]
    result = result.sort_values(by="ev_per_dollar", ascending=False).reset_index(drop=True)
    return result




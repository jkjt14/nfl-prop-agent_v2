"""Static configuration for the prop model application."""

from __future__ import annotations

from typing import Final

# Sportsbooks we include when calculating market averages and consensus lines.
MA_BOOKS: Final[list[str]] = [
    "DraftKings",
    "FanDuel",
    "BetMGM",
    "Caesars",
    "ESPN BET",
    "Fanatics",
    "Bally Bet",
]

# Player prop market identifiers supported by the analytics toolkit.
MARKETS: Final[list[str]] = [
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

# Minimum American odds (e.g., heavy favorite) allowed when ingesting lines.
ODDS_MIN: Final[int] = -200
# Maximum American odds (e.g., longshot) allowed when ingesting lines.
ODDS_MAX: Final[int] = 500

# Minimum number of books that must post a line before evaluating the prop.
MIN_BOOKS: Final[int] = 3
# Highest acceptable combined vig when consolidating market prices.
MAX_VIG: Final[float] = 0.06

# Minimum expected value to flag props for a shortlist review.
SHORTLIST_EV: Final[float] = 0.03
# Minimum expected value to issue a betting recommendation.
RECOMMEND_EV: Final[float] = 0.05
# Z-score threshold for highlighting moderate yardage edges.
Z_YARDS: Final[float] = 0.40
# Z-score threshold for highlighting strong yardage edges.
Z_YARDS_STRONG: Final[float] = 0.65
# Z-score threshold for highlighting moderate reception edges.
Z_REC: Final[float] = 0.55
# Z-score threshold for highlighting strong reception edges.
Z_REC_STRONG: Final[float] = 0.80

# Total bankroll units assumed for staking calculations.
BANKROLL_UNITS: Final[int] = 100
# Fraction of the Kelly stake to deploy for recommended bets.
KELLY_MULTIPLIER: Final[float] = 0.5

# Injury statuses that lead us to drop the prop entirely.
INJURY_DROP_STATUSES: Final[set[str]] = {"OUT", "SUSP"}
# Injury statuses that instruct the staking model to halve the wager size.
INJURY_HALF_STATUSES: Final[set[str]] = {"Q", "D"}

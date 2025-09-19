"""Command-line interface for running the prop model workflow."""

from __future__ import annotations

import argparse
import logging
import os
from typing import Iterable, Sequence

import pandas as pd

from . import config
from .engine import join_and_score
from .io import export_csv, load_projections, timestamped_path
from .odds_api import get_event_player_props, get_upcoming_nfl_events
from .report import format_top_table, notify_slack


def _log_level_from_env() -> int:
    level_name = os.getenv("PROP_MODEL_LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


logging.basicConfig(
    level=_log_level_from_env(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

LOGGER = logging.getLogger(__name__)

_DEFAULT_OUTPUT_DIR = "out"
_DEFAULT_OUTPUT_STEM = "edges"


def _str_to_bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "t", "1", "yes", "y"}:
        return True
    if text in {"false", "f", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("Expected a boolean value (true/false)")


def _event_identifier(event: dict[str, object]) -> str | None:
    for key in ("id", "event_id"):
        value = event.get(key)
        if value:
            return str(value)
    return None


def _event_label(event: dict[str, object]) -> str:
    name = event.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()

    home = event.get("home_team") or event.get("home")
    away = event.get("away_team") or event.get("away")

    if isinstance(home, str) and isinstance(away, str):
        return f"{away.strip()} at {home.strip()}"
    if isinstance(home, str):
        return home.strip()
    if isinstance(away, str):
        return away.strip()

    identifier = _event_identifier(event)
    return identifier or "Unknown event"


def _filter_ma_books(df: pd.DataFrame, enabled: bool) -> pd.DataFrame:
    if not enabled or df.empty:
        return df
    ma_titles = {title.lower() for title in config.MA_BOOKS}
    mask = df["bookmaker_title"].astype(str).str.lower().isin(ma_titles)
    filtered = df.loc[mask].reset_index(drop=True)
    LOGGER.info(
        "Filtered odds to Massachusetts books (%s -> %s rows).",
        len(df),
        len(filtered),
    )
    return filtered


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the prop model against live odds.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Load projections, fetch odds, and generate an edge report.",
    )
    run_parser.add_argument(
        "--projections",
        required=True,
        help="Path to the projections CSV/XLSX file.",
    )
    run_parser.add_argument(
        "--markets",
        nargs="+",
        choices=sorted(config.MARKETS),
        required=True,
        help="List of player prop markets to request from The Odds API.",
    )
    run_parser.add_argument(
        "--ma-books",
        type=_str_to_bool,
        default=True,
        metavar="{true,false}",
        help="Filter odds to the Massachusetts-approved books (default: true).",
    )
    run_parser.add_argument(
        "--slack",
        type=_str_to_bool,
        default=False,
        metavar="{true,false}",
        help="Send the top picks to Slack using SLACK_WEBHOOK_URL (default: false).",
    )
    run_parser.add_argument(
        "--slack-webhook",
        default=None,
        help="Override the Slack webhook URL (defaults to SLACK_WEBHOOK_URL env var).",
    )
    run_parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of picks to include in summaries and Slack notifications.",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    return parser.parse_args(argv)


def _fetch_odds_for_events(
    events: Iterable[dict[str, object]],
    markets: Sequence[str],
    *,
    ma_books_only: bool = True,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for event in events:
        event_id = _event_identifier(event)
        if not event_id:
            LOGGER.info("Skipping event missing an identifier: %s", event)
            continue

        label = _event_label(event)
        LOGGER.info("Fetching player props for %s (%s).", label, event_id)
        event_df = get_event_player_props(event_id, markets, ma_books_only=ma_books_only)
        if event_df.empty:
            LOGGER.info("No props returned for %s.", label)
            continue

        frames.append(event_df)
        LOGGER.info("Collected %s rows for %s.", len(event_df), label)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True, sort=False)
    LOGGER.info(
        "Aggregated %s odds rows across %s events.",
        len(combined),
        len(frames),
    )
    return combined


def _determine_slack_webhook(args: argparse.Namespace) -> str | None:
    if getattr(args, "slack_webhook", None):
        return str(args.slack_webhook)
    return os.getenv("SLACK_WEBHOOK_URL")


def run_workflow(args: argparse.Namespace) -> pd.DataFrame:
    LOGGER.info("Loading projections from %s", args.projections)
    projections = load_projections(args.projections)
    LOGGER.info("Loaded %s projection rows for %s players.", len(projections), projections["player"].nunique())

    LOGGER.info("Fetching upcoming NFL events from The Odds API.")
    events = get_upcoming_nfl_events()
    if not events:
        LOGGER.info("No upcoming events returned. Exiting early.")
        edges = pd.DataFrame()
    else:
        LOGGER.info("Received %s events. Requesting markets: %s", len(events), ", ".join(args.markets))
        odds = _fetch_odds_for_events(events, args.markets, ma_books_only=args.ma_books)
        odds = _filter_ma_books(odds, args.ma_books)
        edges = join_and_score(projections, odds)

    if edges.empty:
        LOGGER.info("No edges identified at this time.")
    else:
        LOGGER.info("Computed %s edges.", len(edges))
        table = format_top_table(edges, n=max(1, min(args.top_n, len(edges))))
        LOGGER.info("Top picks:\n%s", table)

    output_path = timestamped_path(_DEFAULT_OUTPUT_DIR, _DEFAULT_OUTPUT_STEM)
    export_csv(edges, output_path)
    LOGGER.info("Edge report saved to %s", output_path)

    if args.slack:
        webhook = _determine_slack_webhook(args)
        if not webhook:
            LOGGER.warning("Slack enabled but no webhook URL provided.")
        else:
            LOGGER.info("Sending top %s picks to Slack.", args.top_n)
            notify_slack(edges, webhook, n=args.top_n)

    return edges


def main(argv: Sequence[str] | None = None) -> pd.DataFrame:
    args = parse_args(argv)
    if args.command != "run":  # pragma: no cover - defensive programming
        raise ValueError(f"Unknown command: {args.command}")
    return run_workflow(args)


if __name__ == "__main__":  # pragma: no cover - entry point for manual execution
    main()

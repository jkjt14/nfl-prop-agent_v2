"""Reporting utilities for summarising prop model recommendations."""

from __future__ import annotations

import logging
import math
from typing import Sequence

import pandas as pd
import requests

from .io import export_csv

LOGGER = logging.getLogger(__name__)

_REQUIRED_COLUMNS: tuple[str, ...] = (
    "player",
    "market",
    "side",
    "line",
    "price_american",
    "ev_per_dollar",
    "z_score",
    "unit_size",
)

__all__ = ["format_top_table", "notify_slack", "export_csv"]


def _normalize_string(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _format_float(value: float) -> str:
    if math.isfinite(value) and math.isclose(value, round(value)):
        return f"{int(round(value))}"
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def _format_numeric(value: object) -> str:
    if value is None:
        return "-"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        text = _normalize_string(value)
        return text or "-"
    if math.isnan(numeric):
        return "-"
    return _format_float(numeric)


def _format_odds(value: object) -> str:
    if value is None:
        return "-"
    try:
        integer = int(float(value))
    except (TypeError, ValueError):
        text = _normalize_string(value)
        return text or "-"
    return f"{integer:+d}" if integer > 0 else f"{integer:d}"


def _format_percent(value: object) -> str:
    if value is None:
        return "-"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        text = _normalize_string(value)
        return text or "-"
    if math.isnan(numeric):
        return "-"
    return f"{numeric * 100:.1f}"


def _format_units(value: object) -> str:
    if value is None:
        return "-"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        text = _normalize_string(value)
        return text or "-"
    if math.isnan(numeric):
        return "-"
    text = f"{numeric:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def _prepare_top(df: pd.DataFrame, n: int) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=_REQUIRED_COLUMNS)

    missing = [column for column in _REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {', '.join(missing)}")

    ordered = df.sort_values(by="ev_per_dollar", ascending=False, na_position="last")
    return ordered.head(n).reset_index(drop=True)


def _compute_widths(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[int]:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    return widths


def _format_rows(rows: Sequence[Sequence[str]], widths: Sequence[int]) -> list[str]:
    formatted: list[str] = []
    for row in rows:
        formatted.append(" ".join(value.ljust(width) for value, width in zip(row, widths)))
    return formatted


def _render_table(top: pd.DataFrame) -> str:
    if top.empty:
        return "No picks available."

    headers = ["Player", "Market", "Side", "Line", "Odds", "EV%", "z", "Units"]
    rows: list[list[str]] = []

    for _, row in top.iterrows():
        player = _normalize_string(row["player"])
        market = _normalize_string(row["market"])
        side = _normalize_string(row["side"]).upper()
        line = _format_numeric(row["line"])
        odds = _format_odds(row["price_american"])
        ev = _format_percent(row["ev_per_dollar"])
        z_value = _format_numeric(row["z_score"])
        units = _format_units(row["unit_size"])
        rows.append([player, market, side, line, odds, ev, z_value, units])

    widths = _compute_widths(headers, rows)
    header_line = " ".join(header.ljust(width) for header, width in zip(headers, widths))
    separator_line = " ".join("-" * width for width in widths)
    body_lines = _format_rows(rows, widths)

    return "\n".join([header_line, separator_line, *body_lines])


def format_top_table(df: pd.DataFrame, n: int = 20) -> str:
    """Return a compact fixed-width table summarising the top ``n`` picks."""

    top = _prepare_top(df, n)
    return _render_table(top)


def notify_slack(df: pd.DataFrame, webhook_url: str, n: int = 10) -> None:
    """Post the top ``n`` picks to Slack using an incoming webhook."""

    if not webhook_url:
        LOGGER.info("Slack webhook URL not provided; skipping notification.")
        return

    top = _prepare_top(df, n)
    if top.empty:
        LOGGER.info("No picks to notify Slack about.")
        return

    table = _render_table(top)
    message = f"Top {len(top)} prop model picks\n```\n{table}\n```"

    try:
        response = requests.post(webhook_url, json={"text": message}, timeout=5)
        if response.status_code >= 400:
            LOGGER.error(
                "Slack webhook responded with status %s: %s", response.status_code, response.text
            )
    except requests.RequestException as exc:
        LOGGER.error("Failed to send Slack notification: %s", exc)

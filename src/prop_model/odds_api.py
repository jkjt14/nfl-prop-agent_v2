"""Utilities for retrieving player prop odds from The Odds API."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Iterable

import pandas as pd
import requests
from dotenv import load_dotenv

from .config import MA_BOOKS

load_dotenv()

_LOGGER = logging.getLogger(__name__)
_BASE_URL = "https://api.the-odds-api.com/v4"
_ODDS_COLUMNS = [
    "event_id",
    "event_start",
    "player",
    "team",
    "market",
    "side",
    "line",
    "price_american",
    "bookmaker_title",
    "last_update",
]


def _get_api_key() -> str:
    """Fetch the Odds API key from the environment."""

    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ODDS_API_KEY environment variable is required to call The Odds API."
        )
    return api_key


def _request_with_retries(url: str, params: dict[str, Any]) -> requests.Response:
    """Execute a GET request with retries and exponential backoff."""

    max_attempts = 5
    backoff = 1.0

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, params=params, timeout=15)
        except requests.RequestException as exc:  # pragma: no cover - network failures rare
            if attempt == max_attempts:
                raise RuntimeError(f"Request to {url} failed after {max_attempts} attempts") from exc

            _LOGGER.warning(
                "Request to %s failed on attempt %s/%s due to %s. Retrying in %.1fs.",
                url,
                attempt,
                max_attempts,
                exc,
                backoff,
            )
            time.sleep(backoff)
            backoff *= 2
            continue

        if response.status_code == 429:
            retry_after_header = response.headers.get("Retry-After")
            retry_after = float(retry_after_header) if retry_after_header else 0.0
            sleep_for = max(backoff, retry_after)

            if attempt == max_attempts:
                response.raise_for_status()

            _LOGGER.warning(
                "Rate limited by Odds API (429). Sleeping for %.1fs before retry %s/%s.",
                sleep_for,
                attempt + 1,
                max_attempts,
            )
            time.sleep(sleep_for)
            backoff *= 2
            continue

        if response.ok:
            return response

        if attempt == max_attempts:
            response.raise_for_status()

        _LOGGER.warning(
            "Request to %s returned status %s. Retrying in %.1fs.",
            url,
            response.status_code,
            backoff,
        )
        time.sleep(backoff)
        backoff *= 2

    raise RuntimeError(f"Request to {url} failed after {max_attempts} attempts")


def _is_ma_book(bookmaker_title: str) -> bool:
    """Return True when the bookmaker is one of the Massachusetts offerings."""

    title_norm = bookmaker_title.lower()
    return any(ma_book.lower() in title_norm for ma_book in MA_BOOKS)


def _safe_float(value: Any) -> float:
    """Safely convert a value to float, returning NaN when conversion fails."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _safe_int(value: Any) -> int | None:
    """Safely convert a value to an integer if possible."""

    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_upcoming_nfl_events() -> list[dict[str, Any]]:
    """Retrieve the list of upcoming NFL events from The Odds API."""

    api_key = _get_api_key()
    url = f"{_BASE_URL}/sports/americanfootball_nfl/events"
    params = {"apiKey": api_key}

    _LOGGER.info("Requesting upcoming NFL events from The Odds API.")
    response = _request_with_retries(url, params)

    try:
        events = response.json()
    except ValueError as exc:  # pragma: no cover - unexpected payload
        raise RuntimeError("Failed to decode events response from The Odds API") from exc

    if not isinstance(events, list):  # pragma: no cover - defensive check
        raise RuntimeError("Unexpected events payload received from The Odds API")

    _LOGGER.info("Fetched %s upcoming NFL events from The Odds API.", len(events))
    return events


def get_event_player_props(
    event_id: str,
    markets: Iterable[str],
    *,
    regions: str = "us",
    odds_format: str = "american",
) -> pd.DataFrame:
    """Retrieve player prop odds for a specific event."""

    market_list = list(markets)
    if not market_list:
        _LOGGER.info("No markets requested for event %s; returning empty DataFrame.", event_id)
        return pd.DataFrame(columns=_ODDS_COLUMNS)

    api_key = _get_api_key()
    url = f"{_BASE_URL}/sports/americanfootball_nfl/events/{event_id}/odds"
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": ",".join(sorted(set(market_list))),
        "oddsFormat": odds_format,
    }

    _LOGGER.info(
        "Requesting player props for event %s (markets=%s, regions=%s).",
        event_id,
        params["markets"],
        regions,
    )
    response = _request_with_retries(url, params)

    try:
        payload = response.json()
    except ValueError as exc:  # pragma: no cover - unexpected payload
        raise RuntimeError("Failed to decode player props response from The Odds API") from exc

    event_start = payload.get("commence_time") or ""
    bookmakers = payload.get("bookmakers") or []

    rows: list[dict[str, Any]] = []
    for bookmaker in bookmakers:
        title = bookmaker.get("title") or ""
        if not title:
            continue
        if not _is_ma_book(title):
            _LOGGER.info("Skipping bookmaker '%s' not in Massachusetts list.", title)
            continue

        bookmaker_last_update = bookmaker.get("last_update") or ""
        for market in bookmaker.get("markets", []):
            market_key = market.get("key", "")
            market_last_update = market.get("last_update") or bookmaker_last_update

            for outcome in market.get("outcomes", []):
                player = outcome.get("description") or outcome.get("player") or ""
                team = outcome.get("team") or ""
                side = outcome.get("name") or ""
                line_value = _safe_float(outcome.get("point"))
                price = _safe_int(outcome.get("price"))

                rows.append(
                    {
                        "event_id": payload.get("id") or event_id,
                        "event_start": event_start,
                        "player": player,
                        "team": team,
                        "market": market_key,
                        "side": side,
                        "line": line_value,
                        "price_american": price,
                        "bookmaker_title": title,
                        "last_update": market_last_update,
                    }
                )

    df = pd.DataFrame(rows, columns=_ODDS_COLUMNS)
    _LOGGER.info(
        "Retrieved %s player prop rows for event %s after filtering bookmakers.",
        len(df),
        event_id,
    )
    return df


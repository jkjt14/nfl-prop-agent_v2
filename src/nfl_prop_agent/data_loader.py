"""Utilities for loading prop and projection data."""

from __future__ import annotations

import io
from typing import Iterable, List

import pandas as pd
import requests

from .config import get_settings
from .data_models import PlayerProp, Projection
from .exceptions import DataSourceError
from .logging_utils import configure_logging

LOGGER = configure_logging(__name__)


def load_local_csv(filename: str) -> pd.DataFrame:
    """Load a CSV file bundled with the package into a :class:`pandas.DataFrame`."""

    settings = get_settings()
    path = settings.data_directory / filename
    if not path.exists():
        raise DataSourceError(f"Expected data file {path} was not found.")
    LOGGER.debug("Loading local CSV from %s", path)
    return pd.read_csv(path)


def fetch_remote_csv(url: str) -> pd.DataFrame:
    """Fetch a CSV file from a remote URL, raising :class:`DataSourceError` on failure."""

    settings = get_settings()
    LOGGER.info("Fetching remote CSV from %s", url)
    try:
        response = requests.get(url, timeout=settings.http_timeout)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network errors are logged
        LOGGER.error("Failed to download CSV from %s: %s", url, exc)
        raise DataSourceError(f"Failed to download CSV from {url}") from exc
    return pd.read_csv(io.StringIO(response.text))


def _records_to_models(records: Iterable[dict], model_cls) -> List:
    """Convert an iterable of dictionaries to a list of pydantic model instances."""

    return [model_cls(**record) for record in records]


def load_props_from_dataframe(df: pd.DataFrame) -> List[PlayerProp]:
    """Convert a DataFrame into a list of :class:`PlayerProp` models."""

    required_columns = {"player", "team", "market", "line", "odds", "sportsbook"}
    missing = required_columns.difference(df.columns)
    if missing:
        raise DataSourceError(f"Prop DataFrame is missing columns: {', '.join(sorted(missing))}")
    return _records_to_models(df[sorted(required_columns)].to_dict(orient="records"), PlayerProp)


def load_projections_from_dataframe(df: pd.DataFrame) -> List[Projection]:
    """Convert a DataFrame into a list of :class:`Projection` models."""

    required_columns = {"player", "team", "market", "projection", "source"}
    missing = required_columns.difference(df.columns)
    if missing:
        raise DataSourceError(f"Projection DataFrame is missing columns: {', '.join(sorted(missing))}")
    return _records_to_models(df[sorted(required_columns)].to_dict(orient="records"), Projection)


def load_sample_props() -> List[PlayerProp]:
    """Return the bundled sample player props."""

    return load_props_from_dataframe(load_local_csv("props_sample.csv"))


def load_sample_projections() -> List[Projection]:
    """Return the bundled sample projections."""

    return load_projections_from_dataframe(load_local_csv("projections_sample.csv"))

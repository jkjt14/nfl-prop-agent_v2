"""Utilities for reading and writing prop model datasets."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

LOGGER = logging.getLogger(__name__)


def _strip_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _to_float(value: Any) -> float:
    text = _strip_string(value)
    if text == "":
        raise ValueError("Empty string cannot be converted to float")
    return float(text)


def _to_int(value: Any) -> int:
    text = _strip_string(value)
    if text == "":
        raise ValueError("Empty string cannot be converted to int")
    return int(float(text))


REQUIRED_PROJECTION_COLUMNS: tuple[str, ...] = (
    "player",
    "team",
    "position",
    "id",
    "season_year",
    "week",
    "avg_type",
    "pass_yds",
    "pass_yds_sd",
    "pass_tds",
    "pass_tds_sd",
    "pass_int",
    "pass_int_sd",
    "rush_yds",
    "rush_yds_sd",
    "rush_tds",
    "rush_tds_sd",
    "rec",
    "rec_sd",
    "rec_yds",
    "rec_yds_sd",
    "rec_tds",
    "rec_tds_sd",
)

NUMERIC_CASTERS: dict[str, Callable[[Any], Any]] = {
    "season_year": _to_int,
    "week": _to_int,
    "pass_yds": _to_float,
    "pass_yds_sd": _to_float,
    "pass_tds": _to_float,
    "pass_tds_sd": _to_float,
    "pass_int": _to_float,
    "pass_int_sd": _to_float,
    "rush_yds": _to_float,
    "rush_yds_sd": _to_float,
    "rush_tds": _to_float,
    "rush_tds_sd": _to_float,
    "rec": _to_float,
    "rec_sd": _to_float,
    "rec_yds": _to_float,
    "rec_yds_sd": _to_float,
    "rec_tds": _to_float,
    "rec_tds_sd": _to_float,
}


def load_projections(path: str) -> pd.DataFrame:
    """Load projection data from ``path`` normalising headers and numeric fields.

    The loader automatically detects CSV or XLSX files and standardises headers to
    ``snake_case``. Numeric columns are coerced to ``float``/``int`` to ease
    downstream validation.
    """

    source = Path(path)
    if not source.exists():
        msg = f"Projection file not found: {source}"
        LOGGER.error(msg)
        raise FileNotFoundError(msg)

    # Example: df = load_projections("data/projections.csv")
    LOGGER.debug("Loading projections from %s", source)
    dataframe = _read_tabular_file(source)

    column_map = {_strip_string(column).lower(): _to_snake_case(column) for column in dataframe.columns}
    records = dataframe.to_dict(orient="records")

    normalized_rows: list[dict[str, Any]] = []
    for raw_row in records:
        normalized_row = {
            column_map[_strip_string(column).lower()]: raw_row.get(column)
            for column in dataframe.columns
        }
        normalized_rows.append(_coerce_row(normalized_row))

    _ensure_required_columns(normalized_rows)

    return pd.DataFrame(normalized_rows)


def export_csv(df: pd.DataFrame, path: str) -> None:
    """Export ``df`` to ``path`` as CSV."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.debug("Writing %s rows to %s", len(df), destination)
    df.to_csv(destination, index=False)


def timestamped_path(directory: str, stem: str) -> str:
    """Return a CSV path with a timestamped suffix inside ``directory``."""

    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return str(folder / f"{stem}_{timestamp}.csv")


def _read_tabular_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        if hasattr(pd, "read_excel"):
            return pd.read_excel(path)  # type: ignore[attr-defined]
        msg = "Excel support requires pandas with read_excel capability"
        LOGGER.error(msg)
        raise RuntimeError(msg)
    msg = f"Unsupported projection file format: {path.suffix}"
    LOGGER.error(msg)
    raise ValueError(msg)


def _ensure_required_columns(rows: list[dict[str, Any]]) -> None:
    if not rows:
        missing = ", ".join(REQUIRED_PROJECTION_COLUMNS)
        raise ValueError(f"No projection records found; expected columns: {missing}")

    available_columns = set().union(*(row.keys() for row in rows))
    missing_columns = [column for column in REQUIRED_PROJECTION_COLUMNS if column not in available_columns]
    if missing_columns:
        raise ValueError(f"Missing required projection columns: {', '.join(sorted(missing_columns))}")

    for row in rows:
        for column in REQUIRED_PROJECTION_COLUMNS:
            if column not in row:
                raise ValueError(f"Row missing required column '{column}'")
        injury = row.get("injury_status")
        if injury is None or (isinstance(injury, str) and injury.strip() == ""):
            row["injury_status"] = "OK"


def _coerce_row(row: dict[str, Any]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    for key, value in row.items():
        if key in NUMERIC_CASTERS:
            coerced[key] = _coerce_numeric(key, value, NUMERIC_CASTERS[key])
        elif isinstance(value, str):
            coerced[key] = value.strip()
        else:
            coerced[key] = value
    return coerced


def _coerce_numeric(column: str, value: Any, caster: Callable[[Any], Any]) -> Any:
    if value is None:
        raise ValueError(f"Column '{column}' is required but missing a value")
    try:
        return caster(value)
    except (TypeError, ValueError) as error:
        msg = f"Could not coerce column '{column}' with value {value!r}"
        LOGGER.error(msg)
        raise ValueError(msg) from error


def _to_snake_case(value: str) -> str:
    stripped = _strip_string(value)
    result = []
    for character in stripped:
        if character.isalnum():
            result.append(character.lower())
        else:
            result.append("_")
    snake = "".join(result)
    while "__" in snake:
        snake = snake.replace("__", "_")
    return snake.strip("_")

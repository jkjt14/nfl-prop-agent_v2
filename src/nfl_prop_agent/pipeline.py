"""High-level orchestration helpers for building edge reports."""

from __future__ import annotations

from typing import Sequence

import pandas as pd

from .data_loader import (
    fetch_remote_csv,
    load_props_from_dataframe,
    load_projections_from_dataframe,
    load_sample_props,
    load_sample_projections,
)
from .data_models import PlayerProp, Projection
from .edge_calculator import EdgeCalculator
from .logging_utils import configure_logging

LOGGER = configure_logging(__name__)


def build_edge_report(
    props: Sequence[PlayerProp] | None = None,
    projections: Sequence[Projection] | None = None,
) -> pd.DataFrame:
    """Calculate an edge report from provided or sample data."""

    prop_records = list(props) if props is not None else load_sample_props()
    projection_records = list(projections) if projections is not None else load_sample_projections()
    calculator = EdgeCalculator(projection_records)
    return calculator.calculate_edges(prop_records)


def load_props_from_url(url: str) -> Sequence[PlayerProp]:
    """Load prop data from a CSV URL."""

    df = fetch_remote_csv(url)
    return load_props_from_dataframe(df)


def load_projections_from_url(url: str) -> Sequence[Projection]:
    """Load projection data from a CSV URL."""

    df = fetch_remote_csv(url)
    return load_projections_from_dataframe(df)

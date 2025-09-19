"""Streamlit UI for exploring player prop edges."""

from __future__ import annotations

from typing import Sequence

import pandas as pd
import streamlit as st

from .data_loader import (
    load_props_from_dataframe,
    load_projections_from_dataframe,
    load_sample_props,
    load_sample_projections,
)
from .data_models import PlayerProp, Projection
from .edge_calculator import EdgeCalculator


@st.cache_data(show_spinner=False)
def _load_uploaded_data(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    try:
        return pd.read_csv(uploaded_file)
    except Exception as exc:  # pragma: no cover - UI feedback path
        st.error(f"Failed to parse uploaded CSV: {exc}")
        return None


def _records_from_dataframe(df: pd.DataFrame | None, loader) -> Sequence:
    if df is None:
        return ()
    try:
        return loader(df)
    except Exception as exc:  # pragma: no cover - UI feedback path
        st.error(str(exc))
        return ()


def run() -> None:
    """Run the Streamlit application."""

    st.set_page_config(page_title="NFL Prop Edge", layout="wide")
    st.title("NFL Player Prop Edge Dashboard")
    st.write(
        "Upload your own sportsbook and projection CSVs to compute edges, or enjoy the bundled sample data."
    )

    st.sidebar.header("Inputs")
    props_upload = st.sidebar.file_uploader("Sportsbook props CSV", type=["csv"], key="props")
    projections_upload = st.sidebar.file_uploader("Projection CSV", type=["csv"], key="projections")
    min_match_score = st.sidebar.slider("Minimum name match score", min_value=50, max_value=100, value=85)

    sample_props = load_sample_props()
    sample_projections = load_sample_projections()

    props_df = _load_uploaded_data(props_upload)
    projections_df = _load_uploaded_data(projections_upload)

    props_records: Sequence[PlayerProp]
    projections_records: Sequence[Projection]

    props_records = (
        _records_from_dataframe(props_df, load_props_from_dataframe) if props_df is not None else sample_props
    )
    projections_records = (
        _records_from_dataframe(projections_df, load_projections_from_dataframe)
        if projections_df is not None
        else sample_projections
    )

    calculator = EdgeCalculator(projections_records, min_match_score=min_match_score)

    try:
        report = calculator.calculate_edges(props_records)
    except Exception as exc:  # pragma: no cover - UI feedback path
        st.error(str(exc))
        return

    st.dataframe(report, use_container_width=True)
    st.caption(
        "Edge is the difference between the projected over probability (logistic transform) and implied odds probability."
    )


if __name__ == "__main__":  # pragma: no cover - manual execution hook
    run()

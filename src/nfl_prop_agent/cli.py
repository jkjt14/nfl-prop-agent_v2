"""Command-line interface for generating edge reports."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

import pandas as pd

from .data_loader import load_props_from_dataframe, load_projections_from_dataframe
from .data_models import PlayerProp, Projection
from .logging_utils import configure_logging
from .pipeline import build_edge_report

LOGGER = configure_logging(__name__)


def _read_csv_from_arg(value: str) -> pd.DataFrame:
    """Return a :class:`pandas.DataFrame` from a CLI argument value."""

    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return pd.read_csv(value)

    path = Path(value)
    if not path.exists():
        raise FileNotFoundError(f"Not found: {path}")
    return pd.read_csv(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Generate an NFL player prop edge report.")
    parser.add_argument("--props-url", help="CSV URL for sportsbook props", default=None)
    parser.add_argument("--projections-url", help="CSV URL for projections", default=None)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the report as CSV. Printed to stdout when omitted.",
        default=None,
    )
    return parser.parse_args(argv)


def run_cli(argv: Sequence[str] | None = None) -> pd.DataFrame:
    """Run the CLI and return the resulting DataFrame."""

    args = parse_args(argv)
    props: Sequence[PlayerProp] | None = None
    projections: Sequence[Projection] | None = None
    if args.props_url:
        LOGGER.info("Loading props from %s", args.props_url)
        props_df = _read_csv_from_arg(args.props_url)
        props = load_props_from_dataframe(props_df)
    if args.projections_url:
        LOGGER.info("Loading projections from %s", args.projections_url)
        projections_df = _read_csv_from_arg(args.projections_url)
        projections = load_projections_from_dataframe(projections_df)
    report = build_edge_report(props=props, projections=projections)
    if args.output:
        report.to_csv(args.output, index=False)
        LOGGER.info("Wrote report to %s", args.output)
    else:
        print(report.to_string(index=False))
    return report


def main() -> None:
    """Entry-point for the console script."""

    run_cli()


if __name__ == "__main__":  # pragma: no cover - manual execution hook
    main()

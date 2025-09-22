cat > src/nfl_prop_agent/cli.py <<'PY'
"""Command-line interface for generating edge reports."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import pandas as pd

from .data_loader import load_props_from_dataframe, load_projections_from_dataframe
from .data_models import PlayerProp, Projection
from .logging_utils import configure_logging
from .pipeline import build_edge_report

LOGGER = configure_logging(__name__)


def _read_csv_local_or_url(url_or_path):
    """Read CSV from local path or URL.
    Handles http(s)://, file://, and bare filesystem paths.
    """
    from urllib.parse import urlsplit, unquote
    from pathlib import Path as _Path

    u = str(url_or_path)
    parts = urlsplit(u)

    # Remote URLs
    if parts.scheme in ("http", "https"):
        return pd.read_csv(u)

    # file:// URLs
    if parts.scheme == "file":
        netloc = parts.netloc
        path = parts.path or ""
        if netloc in ("", "localhost"):
            fs_path = _Path(unquote(path))
        else:
            fs_path = _Path(unquote("/" + netloc + path))
    else:
        # Bare filesystem path
        fs_path = _Path(unquote(u))

    if not fs_path.is_absolute():
        fs_path = _Path.cwd() / fs_path
    if not fs_path.exists():
        raise FileNotFoundError(f"Not found: {fs_path}")
    return pd.read_csv(fs_path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate an NFL player prop edge report.")
    parser.add_argument(
        "--min-match-score",
        type=int,
        default=None,
        help="Override NPA_MIN_MATCH_SCORE for this run",
    )
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
    import inspect
    import numpy as _np

    args = parse_args(argv)

    # Only pass kwargs that build_edge_report actually accepts.
    extra_kwargs: dict = {}
    try:
        sig = inspect.signature(build_edge_report)
        if args.min_match_score is not None and "min_match_score" in sig.parameters:
            extra_kwargs["min_match_score"] = args.min_match_score
    except Exception:
        # If signature inspection fails, play it safe and don't pass extras.
        pass

    props: Sequence[PlayerProp] | None = None
    projections: Sequence[Projection] | None = None

    if args.props_url:
        LOGGER.info("Loading props from %s", args.props_url)
        props_df = _read_csv_local_or_url(args.props_url)
        props = load_props_from_dataframe(props_df)

    if args.projections_url:
        LOGGER.info("Loading projections from %s", args.projections_url)
        projections_df = _read_csv_local_or_url(args.projections_url)
        projections = load_projections_from_dataframe(projections_df)

    report = build_edge_report(props=props, projections=projections, **extra_kwargs)

    # Ensure "side" column exists (insert just after "odds" if present)
    if "side" not in report.columns:
        insert_at = report.columns.get_loc("odds") + 1 if "odds" in report.columns else len(report.columns)
        if "projected_probability" in report.columns:
            side_vals = _np.where(report["projected_probability"] >= 0.5, "Over", "Under")
        else:
            side_vals = ""
        report.insert(insert_at, "side", side_vals)

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
PY

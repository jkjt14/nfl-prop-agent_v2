cat > src/nfl_prop_agent/cli.py <<'PY'
"""Command-line interface for generating edge reports."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .data_loader import load_props_from_dataframe, load_projections_from_dataframe
from .data_models import PlayerProp, Projection
from .logging_utils import configure_logging
from .pipeline import build_edge_report

LOGGER = configure_logging(__name__)


def _read_csv_local_or_url(url_or_path) -> pd.DataFrame:
    """Read CSV from local path or URL. Supports http(s)://, file://, and bare paths."""
    from urllib.parse import urlsplit, unquote
    from pathlib import Path as _Path

    u = str(url_or_path)
    parts = urlsplit(u)

    if parts.scheme in ("http", "https"):
        return pd.read_csv(u)

    if parts.scheme == "file":
        netloc = parts.netloc
        path = parts.path or ""
        if netloc in ("", "localhost"):
            fs_path = _Path(unquote(path))
        else:
            fs_path = _Path(unquote("/" + netloc + path))
    else:
        fs_path = _Path(unquote(u))

    if not fs_path.is_absolute():
        fs_path = _Path.cwd() / fs_path
    if not fs_path.exists():
        raise FileNotFoundError(f"Not found: {fs_path}")

    return pd.read_csv(fs_path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate an NFL player prop edge report.")
    parser.add_argument("--min-match-score", type=int, default=None,
                        help="Override NPA_MIN_MATCH_SCORE for this run.")
    parser.add_argument("--props-url", help="CSV URL or path for sportsbook props", default=None)
    parser.add_argument("--projections-url", help="CSV URL or path for projections", default=None)
    parser.add_argument("--bankroll", type=float, default=None,
                        help="Bankroll amount for Kelly sizing. If omitted, Kelly columns are not added.")
    parser.add_argument("--kelly-fraction", type=float, default=0.5,
                        help="Kelly fraction (0–1). Default 0.5 (half Kelly).")
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

    # Log the effective logistic slope we are using (settings or env, else 1.0)
    try:
        from .edge_calculator import get_settings as _get_settings
        slope = (getattr(_get_settings(), "logistic_slope", None)
                 or float(os.environ.get("NPA_LOGISTIC_SLOPE", "1.0")))
        LOGGER.info("Using logistic_slope=%s", slope)
    except Exception as e:
        LOGGER.debug("Could not determine logistic_slope: %s", e)

    # Only pass kwargs that build_edge_report actually accepts.
    kwargs: dict = {}
    if getattr(args, "min_match_score", None) is not None:
        kwargs["min_match_score"] = args.min_match_score

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

    report = build_edge_report(props=props, projections=projections, **kwargs)

    # Ensure a 'side' column exists (based on projected_probability)
    if "side" not in report.columns:
        insert_pos = report.columns.get_loc("odds") + 1 if "odds" in report.columns else len(report.columns)
        if "projected_probability" in report.columns:
            report.insert(insert_pos, "side",
                          np.where(report["projected_probability"] >= 0.5, "Over", "Under"))
        else:
            report.insert(insert_pos, "side", "")

    # Optional Kelly sizing columns
    if (getattr(args, "bankroll", None) is not None
            and "projected_probability" in report.columns
            and "odds" in report.columns):
        def _b_from_american(o: float) -> float:
            # profit multiple per 1 unit staked (not including stake)
            return (o / 100.0) if o > 0 else (100.0 / abs(o))

        b = report["odds"].apply(_b_from_american)
        p = report["projected_probability"].clip(0, 1)
        q = 1 - p
        kelly = ((b * p) - q) / b
        kelly = kelly.clip(lower=0.0)
        frac = float(getattr(args, "kelly_fraction", 1.0) or 1.0)
        kelly_used = kelly * frac
        report.insert(len(report.columns), "kelly_fraction", kelly)
        report.insert(len(report.columns), "kelly_fraction_used", kelly_used)
        report.insert(len(report.columns), "kelly_stake", kelly_used * float(args.bankroll))

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

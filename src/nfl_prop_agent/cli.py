cp -f src/nfl_prop_agent/cli.py src/nfl_prop_agent/cli.py.bak.$(date +%s) 2>/dev/null || true

cat > src/nfl_prop_agent/cli.py <<'PY'
"""Command-line interface for generating edge reports."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

import pandas as pd

from .data_loader import load_props_from_dataframe, load_projections_from_dataframe
from .logging_utils import configure_logging
from .pipeline import build_edge_report

LOGGER = configure_logging(__name__)


def _read_csv_local_or_url(path_or_url: str) -> pd.DataFrame:
    return pd.read_csv(path_or_url)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an NFL player prop edge report.")
    parser.add_argument("--min-match-score", type=int, default=None,
                        help="Override NPA_MIN_MATCH_SCORE for this run.")
    parser.add_argument("--props-url", help="CSV URL or path for sportsbook props", default=None)
    parser.add_argument("--projections-url", help="CSV URL or path for projections", default=None)
    parser.add_argument("--bankroll", type=float, default=None,
                        help="Bankroll for Kelly sizing. If omitted, Kelly columns are not added.")
    parser.add_argument("--kelly-fraction", type=float, default=0.5,
                        help="Kelly fraction (0–1). Default 0.5 (half Kelly).")
    parser.add_argument("--output", type=Path,
                        help="Optional path to write the report as CSV. Printed to stdout when omitted.",
                        default=None)
    return parser.parse_args(argv)


def run_cli(argv: Sequence[str] | None = None) -> pd.DataFrame:
    args = parse_args(argv)

    # Log the effective logistic slope (settings or env, else 1.0)
    try:
        from .edge_calculator import get_settings as _get_settings
        slope = (getattr(_get_settings(), "logistic_slope", None)
                 or float(os.environ.get("NPA_LOGISTIC_SLOPE", "1.0")))
        LOGGER.info("Using logistic_slope=%s", slope)
    except Exception:
        pass

    kwargs: dict = {}
    if args.min_match_score is not None:
        kwargs["min_match_score"] = args.min_match_score

    props = None
    projections = None

    if args.props_url:
        LOGGER.info("Loading props from %s", args.props_url)
        props_df = _read_csv_local_or_url(args.props_url)
        props = load_props_from_dataframe(props_df)

    if args.projections_url:
        LOGGER.info("Loading projections from %s", args.projections_url)
        projections_df = _read_csv_local_or_url(args.projections_url)
        projections = load_projections_from_dataframe(projections_df)

    report = build_edge_report(props=props, projections=projections, **kwargs)

    # Kelly sizing (only if bankroll provided and required cols present)
    if (args.bankroll is not None) and ("projected_probability" in report.columns) and ("odds" in report.columns):
        def _b_from_american(o: float) -> float:
            o = float(o)
            return (o / 100.0) if o > 0 else (100.0 / abs(o))

        b = report["odds"].astype(float).map(_b_from_american)
        p = report["projected_probability"].clip(0, 1)
        q = 1 - p
        kelly = ((b * p) - q) / b
        kelly = kelly.clip(lower=0.0)
        frac = float(args.kelly_fraction or 1.0)
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
    run_cli()


if __name__ == "__main__":
    main()
PY

# normalize, clear caches, compile-check, reinstall
sed -i 's/\r$//' src/nfl_prop_agent/cli.py
sed -i 's/\t/    /g' src/nfl_prop_agent/cli.py
find src -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find src -name '*.pyc' -delete 2>/dev/null || true

python - <<'PY'
import compileall, sys
ok = compileall.compile_file('src/nfl_prop_agent/cli.py', quiet=1)
print("OK" if ok else "FAIL"); sys.exit(0 if ok else 1)
PY

pip uninstall -y nfl-prop-agent
pip install -e .

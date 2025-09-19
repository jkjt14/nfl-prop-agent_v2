# NFL Prop Edge Toolkit

A modular, testable Python project for analyzing NFL player prop markets. The toolkit includes data models, loading helpers, edge calculation utilities, a command-line workflow, and an optional Streamlit dashboard for quick exploration.

## Features

- Typed data models built with [Pydantic](https://docs.pydantic.dev/) for sportsbook props and projections.
- Fuzzy player matching via [RapidFuzz](https://github.com/maxbachmann/RapidFuzz) with configurable thresholds.
- Edge calculation that combines implied odds probability with projection-based probabilities.
- CLI for generating CSV reports from local files or remote URLs.
- Streamlit interface for interactive exploration.
- Sample datasets for immediate experimentation.
- Comprehensive unit tests.
- Lightweight stand-ins for third-party libraries (pandas, pydantic, rapidfuzz, requests, streamlit) enable execution in
  network-restricted sandboxes while preserving their public APIs for downstream replacement.

## Getting Started

### Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Environment Variables

Configuration values can be supplied through environment variables using a `.env` file. All keys are prefixed with `NFL_PROP_`. Notable options:

- `NFL_PROP_MIN_MATCH_SCORE`: Override the default minimum RapidFuzz score (85).
- `NFL_PROP_LOGISTIC_SLOPE`: Adjust the logistic probability slope.
- `NFL_PROP_LOG_LEVEL`: Logging level (default `INFO`).

### CLI Usage

Generate an edge report using the bundled sample data:

```bash
python -m nfl_prop_agent.cli
```

Specify custom CSV URLs and write the report to disk:

```bash
python -m nfl_prop_agent.cli --props-url https://example.com/props.csv \
    --projections-url https://example.com/projections.csv \
    --output report.csv
```

CSV headers must match the columns in the sample data found in `src/nfl_prop_agent/data/`.

### Streamlit App

```bash
streamlit run src/nfl_prop_agent/streamlit_app.py
```

Upload sportsbook and projection CSVs or rely on the bundled samples to visualize calculated edges.

### Tests

```bash
pytest
```

## Project Structure

```
src/nfl_prop_agent/
├── cli.py              # Command-line interface
├── config.py           # Settings and environment handling
├── data/               # Sample CSV data
├── data_loader.py      # CSV loading utilities
├── data_models.py      # Pydantic models
├── edge_calculator.py  # Matching and edge calculations
├── pipeline.py         # High-level orchestration helpers
└── streamlit_app.py    # Streamlit dashboard
```

## License

This project is provided without any specific license.

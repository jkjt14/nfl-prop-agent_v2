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

### Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add ODDS_API_KEY
```

The `.env` file is used by both the CLI and the Streamlit app. Populate it with your Odds API key and any optional
`NFL_PROP_*` overrides such as `NFL_PROP_MIN_MATCH_SCORE`, `NFL_PROP_LOGISTIC_SLOPE`, or `NFL_PROP_LOG_LEVEL`.

### CLI Usage

- **Quick start:** run `python -m nfl_prop_agent.cli` to calculate edges using the bundled sample datasets.
- **Custom inputs:** supply CSV URLs for sportsbook props and projections. The command below uses an absolute output path
  so you can see a "real" file location in the working tree.

  ```bash
  python -m nfl_prop_agent.cli \
    --props-url https://example.com/props.csv \
    --projections-url https://example.com/projections.csv \
    --output $(pwd)/reports/week01_edges.csv
  ```

  The CLI expects HTTP(S) URLs—host local files with a lightweight server (for example `python -m http.server`) before
  pointing the flags at them. CSV headers must match the samples in `src/nfl_prop_agent/data/` and the additional
  projections provided in `data/sample_projections.csv`.

### Streamlit Usage

Launch the live workflow locally:

```bash
streamlit run app.py
```

The app loads projections via `nfl_prop_agent.data_loader`, fetches odds from The Odds API, and publishes summaries plus Slack-ready
messages.

### How to add name overrides

Manual overrides help reconcile players who are tough to match via fuzzy logic. Create `data/manual_overrides.csv` with
the exact columns `player_left,team_left,pos_left,player_right,team_right,pos_right`. Each row describes how a record
from the sportsbook feed (`*_left`) should be rewritten to line up with your projection feed (`*_right`). The
`prop_model.mapping` module automatically loads the file, normalises the names/teams/positions, and uses the override
when calculating join pairs. Restart the CLI or Streamlit session after editing the CSV so the changes are picked up.

### Notes on rate limits & retries

- The Odds API endpoints are queried with exponential backoff (up to five attempts) whenever HTTP errors or rate limits
  occur. `Retry-After` headers are honoured, and failures are logged so you can monitor noisy conditions.
- Respect the vendor’s quota—large batch jobs should be staggered or cached locally to avoid repeated fetches.
- When rate limits are hit repeatedly, expect increased latency inside the Streamlit app while the retry logic sleeps.

### Troubleshooting FAQ

- **No odds returned:** confirm `ODDS_API_KEY` is present and valid, verify the requested markets exist in
  `nfl_prop_agent.config.MARKETS`, and check The Odds API status page for outages.
- **Unmatched player names:** ensure both feeds share markets, update `data/manual_overrides.csv`, or lower the
  `NFL_PROP_MIN_MATCH_SCORE` environment variable for more permissive fuzzy matching.
- **Missing projection standard deviation:** the staking model requires `*_sd` columns (for example `rush_yds_sd`). If a
  feed does not provide them, fill the values manually or drop the affected market before running reports.
- **CLI errors when pointing to local files:** the CLI downloads from URLs. Start a simple HTTP server in the directory
  that contains your CSVs (`python -m http.server 8000`) and use `http://localhost:8000/...` paths instead of `file://`.
- **Streamlit session looks stale:** click the “Clear cache” button in the app sidebar or rerun the script to ensure new
  odds/projections are loaded.

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

"""Streamlit front-end for the live NFL prop model workflow."""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from prop_model import config  # noqa: E402
from prop_model.engine import join_and_score  # noqa: E402
from prop_model.io import load_projections  # noqa: E402
from prop_model.odds_api import (  # noqa: E402
    get_event_player_props,
    get_upcoming_nfl_events,
)
from prop_model.report import notify_slack  # noqa: E402


RESULT_COLUMNS = ["tier", "player", "market", "side", "line", "odds", "EV%", "z", "units"]


def _ensure_session_defaults() -> None:
    defaults = {
        "results": None,
        "odds_rows": 0,
        "events_count": 0,
        "coverage": None,
        "status": None,
        "slack_messages": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_results() -> None:
    st.session_state["results"] = None
    st.session_state["odds_rows"] = 0
    st.session_state["events_count"] = 0
    st.session_state["coverage"] = None
    st.session_state["slack_messages"] = []


def _event_identifier(event: dict[str, object]) -> str | None:
    for key in ("id", "event_id"):
        value = event.get(key)
        if value:
            return str(value)
    return None


def _event_label(event: dict[str, object]) -> str:
    name = event.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()

    home = event.get("home_team") or event.get("home")
    away = event.get("away_team") or event.get("away")

    if isinstance(home, str) and isinstance(away, str):
        return f"{away.strip()} at {home.strip()}"
    if isinstance(home, str):
        return home.strip()
    if isinstance(away, str):
        return away.strip()

    identifier = _event_identifier(event)
    return identifier or "Unknown event"


def _load_uploaded_projections(uploaded_file) -> pd.DataFrame:
    suffix = Path(uploaded_file.name).suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name

    try:
        return load_projections(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _fetch_odds(markets: Iterable[str], ma_books_only: bool) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    events = get_upcoming_nfl_events()
    frames: list[pd.DataFrame] = []

    for event in events:
        event_id = _event_identifier(event)
        if not event_id:
            continue
        event_df = get_event_player_props(event_id, markets, ma_books_only=ma_books_only)
        if event_df.empty:
            continue
        event_df = event_df.copy()
        event_df["event_label"] = _event_label(event)
        frames.append(event_df)

    if not frames:
        return pd.DataFrame(), events

    combined = pd.concat(frames, ignore_index=True, sort=False)
    return combined, events


def _prepare_display(edges: pd.DataFrame | None) -> pd.DataFrame:
    if edges is None or edges.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    required = [
        "tier",
        "player",
        "market",
        "side",
        "line",
        "price_american",
        "ev_per_dollar",
        "z_score",
        "unit_size",
    ]
    missing = [column for column in required if column not in edges.columns]
    if missing:
        raise ValueError(f"Edge results missing required columns: {', '.join(missing)}")

    display = pd.DataFrame(
        {
            "tier": edges["tier"],
            "player": edges["player"],
            "market": edges["market"],
            "side": edges["side"].astype(str).str.upper(),
            "line": edges["line"].astype(float).round(2),
            "odds": edges["price_american"].astype(int),
            "EV%": (edges["ev_per_dollar"] * 100).round(1),
            "z": edges["z_score"].astype(float).round(2),
            "units": edges["unit_size"].astype(float).round(2),
        }
    )
    display = display.sort_values(by="EV%", ascending=False, ignore_index=True)
    return display[RESULT_COLUMNS]


@contextlib.contextmanager
def _config_overrides(overrides: dict[str, float]) -> Iterator[None]:
    original: dict[str, float] = {}
    try:
        for key, value in overrides.items():
            if not hasattr(config, key):
                continue
            original[key] = getattr(config, key)
            setattr(config, key, value)
        yield
    finally:
        for key, value in original.items():
            setattr(config, key, value)


def _render_status_messages() -> None:
    status = st.session_state.get("status")
    if status:
        level, message = status
        if level == "success":
            st.success(message)
        elif level == "warning":
            st.warning(message)
        elif level == "error":
            st.error(message)
        else:
            st.info(message)

    for level, message in st.session_state.get("slack_messages", []):
        if level == "success":
            st.success(message)
        elif level == "warning":
            st.warning(message)
        elif level == "error":
            st.error(message)
        else:
            st.info(message)


def main() -> None:
    st.set_page_config(page_title="NFL Prop Model", layout="wide")
    _ensure_session_defaults()

    st.title("NFL Prop Model - Live Edge Finder")
    st.write(
        "Upload a projection CSV, pull the latest sportsbook lines, and identify plus-EV props in seconds."
    )

    st.sidebar.header("Filters")
    ma_books_only = st.sidebar.checkbox("MA books only", value=True)
    markets = st.sidebar.multiselect(
        "Markets",
        options=config.MARKETS,
        default=config.MARKETS,
        help="Markets requested from The Odds API.",
    )

    st.sidebar.header("Threshold overrides")
    shortlist_ev_pct = st.sidebar.slider(
        "Shortlist EV threshold (%)",
        min_value=0.0,
        max_value=10.0,
        value=float(config.SHORTLIST_EV * 100),
        step=0.1,
    )
    recommend_ev_pct = st.sidebar.slider(
        "Recommendation EV threshold (%)",
        min_value=0.0,
        max_value=15.0,
        value=float(config.RECOMMEND_EV * 100),
        step=0.1,
    )
    yard_z = st.sidebar.slider(
        "Yard markets z threshold",
        min_value=0.0,
        max_value=2.5,
        value=float(config.Z_YARDS),
        step=0.05,
    )
    yard_z_strong = st.sidebar.slider(
        "Yard markets strong z threshold",
        min_value=0.0,
        max_value=3.0,
        value=float(config.Z_YARDS_STRONG),
        step=0.05,
    )
    rec_z = st.sidebar.slider(
        "Reception markets z threshold",
        min_value=0.0,
        max_value=2.5,
        value=float(config.Z_REC),
        step=0.05,
    )
    rec_z_strong = st.sidebar.slider(
        "Reception markets strong z threshold",
        min_value=0.0,
        max_value=3.0,
        value=float(config.Z_REC_STRONG),
        step=0.05,
    )

    st.sidebar.header("Slack notifications")
    send_slack = st.sidebar.checkbox("Send Slack update", value=False)
    default_webhook = os.getenv("SLACK_WEBHOOK_URL", "")
    slack_url = st.sidebar.text_input(
        "Slack webhook URL",
        value=default_webhook,
        disabled=not send_slack,
        help="Leave blank to skip Slack notifications.",
    )

    st.subheader("Projections input")
    uploaded_file = st.file_uploader("Upload projections CSV", type=["csv"])
    run_clicked = st.button("Fetch Odds & Compute EV", type="primary")

    if run_clicked:
        st.session_state["status"] = None
        st.session_state["slack_messages"] = []

        if not markets:
            _reset_results()
            st.session_state["status"] = (
                "warning",
                "Select at least one market before requesting odds.",
            )
        elif uploaded_file is None:
            _reset_results()
            st.session_state["status"] = (
                "warning",
                "Upload a projections CSV before running the model.",
            )
        else:
            with st.spinner("Loading projections and fetching live odds..."):
                try:
                    projections = _load_uploaded_projections(uploaded_file)
                except Exception as exc:  # pragma: no cover - UI feedback path
                    _reset_results()
                    st.session_state["status"] = (
                        "error",
                        f"Failed to load projections: {exc}",
                    )
                else:
                    try:
                        odds_df, events = _fetch_odds(markets, ma_books_only)
                    except RuntimeError as exc:  # pragma: no cover - network feedback path
                        _reset_results()
                        message = str(exc)
                        if "ODDS_API_KEY" in message:
                            message = (
                                "Missing ODDS_API_KEY environment variable. "
                                "Set it to enable live odds retrieval."
                            )
                        st.session_state["status"] = ("error", message)
                    except Exception as exc:  # pragma: no cover - unexpected path
                        _reset_results()
                        st.session_state["status"] = (
                            "error",
                            f"Unexpected error while fetching odds: {exc}",
                        )
                    else:
                        st.session_state["events_count"] = len(events)
                        st.session_state["odds_rows"] = len(odds_df)

                        if not events:
                            _reset_results()
                            st.session_state["status"] = (
                                "info",
                                "No upcoming NFL events returned by The Odds API.",
                            )
                        elif odds_df.empty:
                            _reset_results()
                            st.session_state["status"] = (
                                "warning",
                                "No odds returned for the selected markets. Try again later.",
                            )
                        else:
                            yard_z_strong_value = max(yard_z_strong, yard_z)
                            rec_z_strong_value = max(rec_z_strong, rec_z)
                            overrides = {
                                "SHORTLIST_EV": shortlist_ev_pct / 100.0,
                                "RECOMMEND_EV": recommend_ev_pct / 100.0,
                                "Z_YARDS": yard_z,
                                "Z_YARDS_STRONG": yard_z_strong_value,
                                "Z_REC": rec_z,
                                "Z_REC_STRONG": rec_z_strong_value,
                            }

                            with _config_overrides(overrides):
                                edges = join_and_score(projections, odds_df)

                            st.session_state["results"] = edges
                            st.session_state["coverage"] = (
                                len(edges) / len(odds_df) if len(odds_df) else None
                            )

                            if edges.empty:
                                st.session_state["status"] = (
                                    "info",
                                    "Odds fetched successfully, but no edges met the thresholds.",
                                )
                            else:
                                st.session_state["status"] = (
                                    "success",
                                    f"Identified {len(edges)} edges across {len(events)} events.",
                                )

                                if send_slack:
                                    slack_messages: list[tuple[str, str]] = []
                                    if slack_url.strip():
                                        try:
                                            notify_slack(edges, slack_url.strip())
                                        except Exception as exc:  # pragma: no cover - webhook failure
                                            slack_messages.append(
                                                (
                                                    "warning",
                                                    f"Failed to send Slack notification: {exc}",
                                                )
                                            )
                                        else:
                                            slack_messages.append(
                                                ("success", "Slack notification sent successfully."),
                                            )
                                    else:
                                        slack_messages.append(
                                            (
                                                "warning",
                                                "Slack notification enabled but no webhook URL provided.",
                                            )
                                        )
                                    st.session_state["slack_messages"] = slack_messages

    display_df = _prepare_display(st.session_state.get("results"))
    if not display_df.empty:
        st.subheader("Edge results")
        st.dataframe(display_df, use_container_width=True)
    elif st.session_state.get("results") is not None:
        st.subheader("Edge results")
        st.dataframe(display_df, use_container_width=True)

    results_df = st.session_state.get("results")
    csv_data = b""
    download_disabled = True
    if isinstance(results_df, pd.DataFrame) and not results_df.empty:
        csv_data = results_df.to_csv(index=False).encode("utf-8")
        download_disabled = False

    st.download_button(
        "Download CSV",
        data=csv_data,
        file_name="prop_edges.csv",
        mime="text/csv",
        disabled=download_disabled,
    )

    coverage = st.session_state.get("coverage")
    odds_rows = st.session_state.get("odds_rows", 0)
    events_count = st.session_state.get("events_count", 0)

    if isinstance(results_df, pd.DataFrame):
        st.caption(
            f"Events processed: {events_count} | Odds rows fetched: {odds_rows}"
        )

    if coverage is not None and odds_rows:
        matched = len(results_df) if isinstance(results_df, pd.DataFrame) else 0
        st.info(f"Matched {matched} of {odds_rows} odds rows ({coverage * 100:.1f}%).")
        if coverage < 0.8:
            st.warning(
                "Fewer than 80% of odds rows matched to projections. Check the projection file and selected markets."
            )

    _render_status_messages()


if __name__ == "__main__":  # pragma: no cover - manual execution hook
    main()

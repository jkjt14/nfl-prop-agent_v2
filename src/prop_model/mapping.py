"""Utility functions for normalizing and joining player data sources."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import List, Sequence, Tuple

import pandas as pd
from rapidfuzz import fuzz, process
import unicodedata

_SUFFIXES = {"jr", "sr", "ii", "iii"}
_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_TEAM_PUNCT_RE = re.compile(r"[^a-z0-9]")

_POS_ALIASES = {
    "HB": "RB",
    "TB": "RB",
    "FB": "RB",
    "RB": "RB",
    "WR": "WR",
    "TE": "TE",
    "QB": "QB",
    "PK": "K",
    "K": "K",
    "P": "P",
    "PR": "ST",
    "KR": "ST",
    "CB": "CB",
    "DB": "DB",
    "S": "S",
    "SS": "S",
    "FS": "S",
    "DE": "DL",
    "DT": "DL",
    "DL": "DL",
    "NT": "DL",
    "OLB": "LB",
    "ILB": "LB",
    "MLB": "LB",
    "LB": "LB",
    "EDGE": "LB",
    "OG": "OL",
    "OT": "OL",
    "OL": "OL",
    "C": "OL",
    "G": "OL",
    "T": "OL",
    "LS": "ST",
    "DST": "DST",
    "DEF": "DST",
}

_MANUAL_OVERRIDE_COLUMNS = {
    "player_left",
    "team_left",
    "pos_left",
    "player_right",
    "team_right",
    "pos_right",
}


def normalize_name(value: str) -> str:
    """Return a normalized representation of a player's name."""
    if value is None:
        return ""
    text = str(value)
    if not text or text.lower() == "nan":
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    tokens: List[str] = [token for token in text.split() if token]
    while tokens and tokens[-1] in _SUFFIXES:
        tokens.pop()
    normalized = " ".join(tokens)
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def _normalize_team(value: str) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text or text.lower() == "nan":
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _TEAM_PUNCT_RE.sub("", text)
    return text


def _normalize_pos(value: str) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text or text.lower() == "nan":
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.upper()
    parts = re.split(r"[\\/,&\s]+", text)
    for part in parts:
        if not part:
            continue
        part = _POS_ALIASES.get(part, part)
        if part:
            return part
    return ""


def canonicalize(
    df: pd.DataFrame,
    name_col: str = "player",
    team_col: str = "team",
    pos_col: str = "position",
) -> pd.DataFrame:
    """Standardize key fields for later matching."""
    result = df.copy()
    for column in (name_col, team_col, pos_col):
        if column not in result.columns:
            raise KeyError(f"'{column}' column is required for canonicalization")

    result["player_norm"] = result[name_col].apply(lambda v: normalize_name(v))
    result["team_norm"] = result[team_col].apply(lambda v: _normalize_team(v))
    result["pos_norm"] = result[pos_col].apply(lambda v: _normalize_pos(v))
    return result


def _load_manual_overrides(path: Path = Path("data/manual_overrides.csv")) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=sorted(_MANUAL_OVERRIDE_COLUMNS))
    overrides = pd.read_csv(path)
    missing = _MANUAL_OVERRIDE_COLUMNS.difference(overrides.columns)
    if missing:
        raise ValueError(
            "Manual override file is missing required columns: "
            + ", ".join(sorted(missing))
        )
    return overrides


def _apply_manual_overrides(
    left: pd.DataFrame,
    right: pd.DataFrame,
    overrides: pd.DataFrame,
) -> List[Tuple[int, int]]:
    manual_pairs: List[Tuple[int, int]] = []
    if overrides.empty:
        return manual_pairs

    left_original = {
        "player": left["player_norm"].copy(),
        "team": left["team_norm"].copy(),
        "pos": left["pos_norm"].copy(),
    }
    right_original = {
        "player": right["player_norm"].copy(),
        "team": right["team_norm"].copy(),
        "pos": right["pos_norm"].copy(),
    }

    for _, override in overrides.iterrows():
        left_player_norm = normalize_name(override["player_left"])
        left_team_norm = _normalize_team(override["team_left"])
        left_pos_norm = _normalize_pos(override["pos_left"])

        right_player_norm = normalize_name(override["player_right"])
        right_team_norm = _normalize_team(override["team_right"])
        right_pos_norm = _normalize_pos(override["pos_right"])

        left_mask = (
            (left_original["player"] == left_player_norm)
            & (left_original["team"] == left_team_norm)
            & (left_original["pos"] == left_pos_norm)
        )
        right_mask = (
            (right_original["player"] == right_player_norm)
            & (right_original["team"] == right_team_norm)
            & (right_original["pos"] == right_pos_norm)
        )

        if not left_mask.any() or not right_mask.any():
            continue

        left_indices = left.index[left_mask]
        right_indices = right.index[right_mask]
        right_index = right_indices[0]

        left.loc[left_indices, "player_norm"] = right_player_norm
        left.loc[left_indices, "team_norm"] = right_team_norm
        left.loc[left_indices, "pos_norm"] = right_pos_norm

        manual_pairs.extend((int(idx), int(right_index)) for idx in left_indices)
    return manual_pairs


def fuzzy_join(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    *,
    left_on: Sequence[str] = ("player_norm", "team_norm", "pos_norm"),
    right_on: Sequence[str] = ("player_norm", "team_norm", "pos_norm"),
    threshold: float = 90,
    name_col: str = "player",
    team_col: str = "team",
    pos_col: str = "position",
) -> pd.DataFrame:
    """Perform a fuzzy join between two dataframes on normalized columns."""
    if len(left_on) < 3 or len(right_on) < 3:
        raise ValueError("fuzzy_join expects player, team, and position columns for matching")
    if len(left_on) != len(right_on):
        raise ValueError("left_on and right_on must have the same length")

    left = canonicalize(left_df, name_col=name_col, team_col=team_col, pos_col=pos_col)
    right = canonicalize(right_df, name_col=name_col, team_col=team_col, pos_col=pos_col)

    overrides = _load_manual_overrides()
    manual_pairs = _apply_manual_overrides(left, right, overrides)

    matched_pairs: List[Tuple[int, int, float, bool]] = []
    matched_right = set()
    matched_left = set()

    for left_idx, right_idx in manual_pairs:
        if right_idx in matched_right or left_idx in matched_left:
            continue
        matched_pairs.append((left_idx, right_idx, 100.0, True))
        matched_right.add(right_idx)
        matched_left.add(left_idx)

    for left_idx, left_row in left.iterrows():
        if left_idx in matched_left:
            continue
        team_val = left_row[left_on[1]] if len(left_on) > 1 else ""
        pos_val = left_row[left_on[2]] if len(left_on) > 2 else ""
        if not team_val or not pos_val:
            continue
        right_subset = right[
            (right[right_on[1]] == team_val) & (right[right_on[2]] == pos_val)
        ]
        if right_subset.empty:
            continue
        choices = {
            idx: value
            for idx, value in right_subset[right_on[0]].items()
            if idx not in matched_right
        }
        if not choices:
            continue
        match = process.extractOne(
            left_row[left_on[0]],
            choices,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold,
        )
        if not match:
            continue
        _, score, right_idx = match
        matched_pairs.append((left_idx, int(right_idx), float(score), False))
        matched_right.add(int(right_idx))
        matched_left.add(left_idx)

    records = []
    for left_idx, right_idx, score, manual in matched_pairs:
        record = {"match_score": score, "manual_override": manual}
        for col in left.columns:
            record[f"left_{col}"] = left.at[left_idx, col]
        for col in right.columns:
            record[f"right_{col}"] = right.at[right_idx, col]
        records.append(record)

    result = pd.DataFrame(records)

    unmatched_left = left.loc[left.index.difference(matched_left)]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("out")
    out_dir.mkdir(parents=True, exist_ok=True)
    unmatched_path = out_dir / f"unmatched_{timestamp}.csv"
    unmatched_left.to_csv(unmatched_path, index=False)

    return result

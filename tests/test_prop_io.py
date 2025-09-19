"""Tests for projection I/O helpers."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from prop_model.io import export_csv, load_projections, timestamped_path


def _write_csv(path: Path, header: str, row: str) -> None:
    path.write_text(f"{header}\n{row}\n", encoding="utf-8")


def test_load_projections_normalises_and_coerces(tmp_path: Path) -> None:
    file_path = tmp_path / "projections.csv"
    header = (
        "Player,Team,Position,ID,Season Year,Week,Avg Type,Pass Yds,Pass Yds SD,"
        "Pass TDs,Pass TDs SD,Pass INT,Pass INT SD,Rush Yds,Rush Yds SD,Rush TDs,"
        "Rush TDs SD,Rec,Rec SD,Rec Yds,Rec Yds SD,Rec TDs,Rec TDs SD"
    )
    row = (
        "Patrick Mahomes,KC,QB,mahomes-1,2024,1,mean,305.5,12.0,2.4,0.8,0.7,0.2,"
        "25.5,5.0,0.3,0.1,0,0,0,0,0,0"
    )
    _write_csv(file_path, header, row)

    frame = load_projections(str(file_path))
    records = frame.to_dict(orient="records")
    assert len(records) == 1
    record = records[0]
    assert record["player"] == "Patrick Mahomes"
    assert record["season_year"] == 2024
    assert record["pass_yds"] == pytest.approx(305.5)
    assert record["injury_status"] == "OK"


def test_load_projections_missing_column_raises(tmp_path: Path) -> None:
    file_path = tmp_path / "bad.csv"
    _write_csv(file_path, "Player,Team", "Amon-Ra St. Brown,DET")

    with pytest.raises(ValueError):
        load_projections(str(file_path))


def test_export_and_timestamp(tmp_path: Path) -> None:
    df = pd.DataFrame([{"player": "Test", "season_year": 2024}])
    destination = tmp_path / "out.csv"

    export_csv(df, str(destination))
    assert destination.exists()

    stamped = timestamped_path(str(tmp_path), "props")
    assert stamped.endswith(".csv")
    assert Path(stamped).parent == tmp_path
    assert re.search(r"props_\d{8}_\d{4}\.csv$", stamped)

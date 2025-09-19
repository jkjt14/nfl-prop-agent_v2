"""Lightweight stand-in for pandas used in restricted execution environments."""

from __future__ import annotations

import csv
from io import StringIO, TextIOBase
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Sequence

PathLike = str | Path


class DataFrame:
    """Minimal tabular data structure supporting the operations required by the project."""

    def __init__(self, data: Iterable[Mapping[str, Any]] | None = None):
        rows = [dict(row) for row in data] if data is not None else []
        self._rows: List[dict[str, Any]] = rows
        self._columns: List[str] = list(rows[0].keys()) if rows else []

    @property
    def columns(self) -> List[str]:
        return list(self._columns)

    def __len__(self) -> int:
        return len(self._rows)

    def __iter__(self):
        return iter(self._rows)

    def __getitem__(self, item: Sequence[str] | str):
        if isinstance(item, list):
            return DataFrame([{column: row.get(column) for column in item} for row in self._rows])
        if isinstance(item, str):
            return [row.get(item) for row in self._rows]
        raise TypeError("Unsupported index type for DataFrame.__getitem__")

    def to_dict(self, orient: str = "records") -> List[dict[str, Any]]:
        if orient != "records":
            raise ValueError("Only 'records' orient is supported in this lightweight implementation.")
        return [dict(row) for row in self._rows]

    def sort_values(self, by: str, ascending: bool = True, inplace: bool = False):
        sorted_rows = sorted(self._rows, key=lambda row: row.get(by), reverse=not ascending)
        if inplace:
            self._rows = sorted_rows
            return None
        return DataFrame(sorted_rows)

    def reset_index(self, drop: bool = False, inplace: bool = False):
        if inplace:
            return None
        return self

    def to_string(self, index: bool = True) -> str:
        if not self._rows:
            return ""
        headers = self._columns
        rows = [" | ".join(headers)]
        for row in self._rows:
            rows.append(" | ".join(str(row.get(column, "")) for column in headers))
        return "\n".join(rows)

    def to_csv(self, path: PathLike, index: bool = False) -> None:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self._columns)
            writer.writeheader()
            for row in self._rows:
                writer.writerow({column: row.get(column) for column in self._columns})

    @property
    def iloc(self) -> "_ILocAccessor":
        return _ILocAccessor(self._rows)


class _ILocAccessor:
    def __init__(self, rows: List[dict[str, Any]]):
        self._rows = rows

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self._rows[index]


def read_csv(path_or_buffer: PathLike | TextIOBase | StringIO) -> DataFrame:
    """Parse CSV data from a file path or file-like object into a :class:`DataFrame`."""

    if isinstance(path_or_buffer, (str, Path)):
        with open(path_or_buffer, "r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return DataFrame(reader)
    if hasattr(path_or_buffer, "read"):
        text = path_or_buffer.read()
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        reader = csv.DictReader(StringIO(text))
        return DataFrame(reader)
    raise TypeError("Unsupported type for read_csv")

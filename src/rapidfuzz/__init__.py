"""Simplified RapidFuzz replacements used for deterministic testing."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable, Sequence, Tuple


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100


class fuzz:
    @staticmethod
    def WRatio(a: str, b: str) -> float:
        return _ratio(a, b)


class process:
    @staticmethod
    def extractOne(query: str, choices: Sequence[str], scorer=fuzz.WRatio) -> Tuple[str, float, int] | None:
        best: Tuple[str, float, int] | None = None
        for index, choice in enumerate(choices):
            score = scorer(query, choice)
            if best is None or score > best[1]:
                best = (choice, score, index)
        return best

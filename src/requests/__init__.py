"""Minimal subset of the requests API using urllib under the hood."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass


class RequestException(Exception):
    """Base exception for HTTP errors."""


@dataclass
class Response:
    status_code: int
    text: str

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            raise RequestException(f"HTTP {self.status_code}")


def get(url: str, timeout: float | None = None) -> Response:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as handle:
            status = getattr(handle, "status", 200)
            text = handle.read().decode("utf-8")
            return Response(status_code=status, text=text)
    except urllib.error.HTTPError as exc:  # pragma: no cover - passthrough
        raise RequestException(str(exc)) from exc
    except urllib.error.URLError as exc:  # pragma: no cover - passthrough
        raise RequestException(str(exc)) from exc

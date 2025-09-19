"""Streamlit stubs enabling local execution without the real library."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


def cache_data(show_spinner: bool | None = None) -> Callable:
    def decorator(func: Callable) -> Callable:
        return func

    return decorator


def set_page_config(**kwargs: Any) -> None:  # pragma: no cover - no-op
    pass


def title(text: str) -> None:  # pragma: no cover - placeholder
    print(text)


def write(text: str) -> None:  # pragma: no cover - placeholder
    print(text)


def dataframe(data: Any, use_container_width: bool = False) -> None:  # pragma: no cover - placeholder
    print("DataFrame:")
    print(getattr(data, "to_string", lambda **_: str(data))())


def caption(text: str) -> None:  # pragma: no cover - placeholder
    print(text)


def error(text: str) -> None:  # pragma: no cover - placeholder
    print(f"ERROR: {text}")


@dataclass
class _Sidebar:
    def header(self, text: str) -> None:  # pragma: no cover - placeholder
        print(text)

    def file_uploader(self, label: str, type: list[str] | None = None, key: str | None = None):  # pragma: no cover - stub
        return None

    def slider(
        self,
        label: str,
        min_value: int,
        max_value: int,
        value: int,
    ) -> int:  # pragma: no cover - stub
        return value


sidebar = _Sidebar()

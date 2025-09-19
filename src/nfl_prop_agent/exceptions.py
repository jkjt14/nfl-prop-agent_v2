"""Custom exception types for the application."""

from __future__ import annotations


class DataSourceError(RuntimeError):
    """Raised when an external data source cannot be reached or parsed."""


class MatchNotFoundError(LookupError):
    """Raised when no projection can be matched to a player prop."""

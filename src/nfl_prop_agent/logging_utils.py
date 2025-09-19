"""Centralized logging configuration helpers."""

from __future__ import annotations

import logging
from typing import Optional

from .config import settings


def configure_logging(name: Optional[str] = None) -> logging.Logger:
    """Return a logger configured with the project defaults."""

    logger = logging.getLogger(name if name else "nfl_prop_agent")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(settings.log_level.upper())
    return logger

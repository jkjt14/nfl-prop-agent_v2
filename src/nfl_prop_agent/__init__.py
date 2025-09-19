"""Top-level package for the NFL prop edge toolkit."""

from .config import settings
from .edge_calculator import EdgeCalculator
from .streamlit_app import run as run_app

__all__ = ["settings", "EdgeCalculator", "run_app"]

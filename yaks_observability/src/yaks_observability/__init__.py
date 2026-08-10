"""yaks-observability — Production-grade OpenTelemetry for FastAPI.

Usage::

    from fastapi import FastAPI
    from yaks_observability import setup

    app = FastAPI()
    setup(app)
"""

from __future__ import annotations

from .config import Environment, ObservabilityConfig
from .setup import setup

__version__ = "1.0.0"

__all__ = [
    "Environment",
    "ObservabilityConfig",
    "setup",
    "__version__",
]

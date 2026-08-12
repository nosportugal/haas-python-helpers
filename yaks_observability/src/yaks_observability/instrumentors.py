"""Graceful degradation: safe imports and resilient OTEL pipeline."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger("yaks_observability.instrumentors")


def safe_import(module_path: str) -> ModuleType | None:
    """Import a module and return None if it is not installed.

    Used for optional downstream instrumentors (sqlalchemy, httpx, requests).
    """
    try:
        return __import__(module_path, fromlist=[""])
    except ImportError:
        logger.debug("Optional module %s not installed; skipping.", module_path)
        return None


def instrument_sqlalchemy(safe_engine: object) -> None:
    """Instrument a SQLAlchemy engine if the instrumentor is available."""
    mod = safe_import("opentelemetry.instrumentation.sqlalchemy")
    if mod is None:
        return
    try:
        instrumentor = mod.SQLAlchemyInstrumentor()
        instrumentor.instrument(engine=safe_engine)
        logger.debug("SQLAlchemy instrumented.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to instrument SQLAlchemy: %s", exc)


def instrument_httpx() -> None:
    """Instrument httpx if available."""
    mod = safe_import("opentelemetry.instrumentation.httpx")
    if mod is None:
        return
    try:
        instrumentor = mod.HTTPXClientInstrumentor()
        instrumentor.instrument()
        logger.debug("httpx instrumented.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to instrument httpx: %s", exc)


def instrument_requests() -> None:
    """Instrument requests if available."""
    mod = safe_import("opentelemetry.instrumentation.requests")
    if mod is None:
        return
    try:
        instrumentor = mod.RequestsInstrumentor()
        instrumentor.instrument()
        logger.debug("requests instrumented.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to instrument requests: %s", exc)


@contextmanager
def suppress_otel_errors():
    """Context manager that swallows OTEL export errors to prevent app crashes."""
    try:
        yield
    except Exception as exc:  # noqa: BLE001
        logger.debug("OTEL operation suppressed error: %s", exc)

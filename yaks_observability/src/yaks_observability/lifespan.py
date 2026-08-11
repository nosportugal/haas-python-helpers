"""FastAPI lifespan integration for graceful OTEL shutdown."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .instrumentation import shutdown_providers

if TYPE_CHECKING:
    from fastapi import FastAPI
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider

logger = logging.getLogger(__name__)


class _LifespanState:
    """Mutable holder for providers so lifespan can shut them down."""

    __slots__ = ("trace_provider", "log_provider", "metric_provider")

    def __init__(self) -> None:
        self.trace_provider: TracerProvider | None = None
        self.log_provider: LoggerProvider | None = None
        self.metric_provider: MeterProvider | None = None


_GLOBAL_STATE: _LifespanState | None = None


def set_lifespan_state(
    trace_provider=None,
    log_provider=None,
    metric_provider=None,
) -> None:
    global _GLOBAL_STATE  # noqa: PLW0603
    if _GLOBAL_STATE is None:
        _GLOBAL_STATE = _LifespanState()
    if trace_provider is not None:
        _GLOBAL_STATE.trace_provider = trace_provider
    if log_provider is not None:
        _GLOBAL_STATE.log_provider = log_provider
    if metric_provider is not None:
        _GLOBAL_STATE.metric_provider = metric_provider


@contextlib.asynccontextmanager
async def _managed_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Yield immediately; shutdown on exit."""
    try:
        yield
    finally:
        if _GLOBAL_STATE is not None:
            shutdown_providers(
                _GLOBAL_STATE.trace_provider,
                _GLOBAL_STATE.log_provider,
                _GLOBAL_STATE.metric_provider,
            )


def attach_lifespan(app: FastAPI) -> None:
    """Replace or wrap the app's lifespan with OTEL shutdown logic.

    If the app already has a lifespan, we chain them: existing first,
    then shutdown.
    """
    existing = app.router.lifespan_context

    if existing is None:
        app.router.lifespan_context = _managed_lifespan
        return

    @contextlib.asynccontextmanager
    async def _chained_lifespan(
        app_inner: FastAPI,
    ) -> AsyncIterator[None]:
        async with contextlib.AsyncExitStack() as stack:
            await stack.enter_async_context(existing(app_inner))
            try:
                yield
            finally:
                if _GLOBAL_STATE is not None:
                    shutdown_providers(
                        _GLOBAL_STATE.trace_provider,
                        _GLOBAL_STATE.log_provider,
                        _GLOBAL_STATE.metric_provider,
                    )

    app.router.lifespan_context = _chained_lifespan

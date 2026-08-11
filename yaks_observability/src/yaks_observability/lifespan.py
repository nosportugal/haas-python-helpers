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


# Per-app state: FastAPI instance id → _LifespanState
_APP_STATE: dict[int, _LifespanState] = {}


def set_lifespan_state(
    trace_provider=None,
    log_provider=None,
    metric_provider=None,
    app_id: int | None = None,
) -> None:
    state = _LifespanState()
    if trace_provider is not None:
        state.trace_provider = trace_provider
    if log_provider is not None:
        state.log_provider = log_provider
    if metric_provider is not None:
        state.metric_provider = metric_provider
    target_id = app_id or id(state)
    _APP_STATE[target_id] = state


def teardown_lifespan_state(app_id: int | None = None) -> None:
    """Remove stored state for an app (useful in tests)."""
    if app_id is not None and app_id in _APP_STATE:
        del _APP_STATE[app_id]


@contextlib.asynccontextmanager
async def _managed_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Yield immediately; shutdown on exit."""
    try:
        yield
    finally:
        state = _APP_STATE.get(id(app))
        if state is not None:
            shutdown_providers(
                state.trace_provider,
                state.log_provider,
                state.metric_provider,
            )
            _APP_STATE.pop(id(app), None)


def attach_lifespan(app: FastAPI) -> None:
    """Replace or wrap the app's lifespan with OTEL shutdown logic.

    If the app already has a lifespan, we chain them: existing first,
    then shutdown.  Guard against duplicate chaining.
    """
    existing = app.router.lifespan_context

    # Already wrapped by us — do not double-wrap
    if getattr(app.router, "_yaks_lifespan_wrapped", False):
        return

    if existing is None:
        app.router.lifespan_context = _managed_lifespan
        app.router._yaks_lifespan_wrapped = True  # type: ignore[attr-defined]
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
                state = _APP_STATE.get(id(app_inner))
                if state is not None:
                    shutdown_providers(
                        state.trace_provider,
                        state.log_provider,
                        state.metric_provider,
                    )
                    _APP_STATE.pop(id(app_inner), None)

    app.router.lifespan_context = _chained_lifespan
    app.router._yaks_lifespan_wrapped = True  # type: ignore[attr-defined]

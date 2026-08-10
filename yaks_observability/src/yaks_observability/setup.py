"""Main entry point: one-call observability setup for FastAPI apps."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .config import ObservabilityConfig
from .graceful_degradation import (
    instrument_httpx,
    instrument_requests,
    instrument_sqlalchemy,
)
from .instrumentation import (
    _init_logging,
    _init_metrics,
    _init_tracing,
    instrument_fastapi,
)
from .lifespan import attach_lifespan, set_lifespan_state
from .logging_config import configure_logging

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup(  # noqa: PLR0913
    app: FastAPI,
    *,
    engine: object | None = None,
    enable_sqlalchemy: bool = True,
    enable_httpx: bool = True,
    enable_requests: bool = True,
    config: ObservabilityConfig | None = None,
) -> ObservabilityConfig:
    """Configure full observability for a FastAPI application.

    This single call enables:
    - Environment-aware structured logging (JSON in prod, text in dev)
    - Health-check log filtering (``/health``, ``/readiness``, etc.)
    - OpenTelemetry traces, logs, and metrics via OTLP/HTTP
    - Distributed tracing (W3C tracecontext + baggage propagation)
    - Downstream auto-instrumentation (SQLAlchemy, httpx, requests)
    - Graceful degradation (missing deps or collector downtime handled silently)
    - Graceful shutdown (force_flush on app lifespan exit)

    Args:
        app: FastAPI application instance.
        engine: SQLAlchemy engine to instrument (requires ``[downstream]`` extra).
        enable_sqlalchemy: Toggle SQLAlchemy instrumentation.
        enable_httpx: Toggle httpx client instrumentation.
        enable_requests: Toggle requests library instrumentation.
        config: Optional pre-built config; otherwise read from environment.

    Returns:
        The resolved :class:`ObservabilityConfig`.
    """
    resolved = config or ObservabilityConfig.from_env()

    # 1. Logging basics (console + health filter)
    configure_logging(resolved)

    # 2. Initialize OTEL providers
    resource = None
    trace_provider = None
    log_provider = None
    metric_provider = None

    if not resolved.testing_mode:
        from .instrumentation import _build_resource  # noqa: PLC0415

        resource = _build_resource(resolved)
        trace_provider = _init_tracing(resolved, resource)
        log_provider = _init_logging(resolved, resource)
        metric_provider = _init_metrics(resolved, resource)

    # 3. Register lifespan shutdown
    set_lifespan_state(trace_provider, log_provider, metric_provider)
    attach_lifespan(app)

    # 4. Instrument FastAPI (ASGI middleware)
    instrument_fastapi(app, resolved)

    # 5. Downstream HTTP client instrumentation
    if enable_httpx:
        instrument_httpx()
    if enable_requests:
        instrument_requests()

    # 6. SQLAlchemy instrumentation (if engine provided)
    if enable_sqlalchemy and engine is not None:
        instrument_sqlalchemy(engine)

    logger.info(
        "Observability setup complete: "
        "env=%s service=%s trace=%s logs=%s metrics=%s",
        resolved.environment.value,
        resolved.service_name,
        trace_provider is not None,
        log_provider is not None,
        metric_provider is not None,
    )
    return resolved

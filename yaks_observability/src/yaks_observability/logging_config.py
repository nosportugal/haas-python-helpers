"""Structured logging setup with OpenTelemetry correlation.

Uses python-json-logger for JSON output and reads trace context injected
by the OTEL LoggingInstrumentor (``otelTraceID``, ``otelSpanID``).
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

# python-json-logger moved the module in v4+; suppress deprecation and import safely
try:
    from pythonjsonlogger.json import JsonFormatter
except ImportError:
    import pythonjsonlogger.jsonlogger

    JsonFormatter = pythonjsonlogger.jsonlogger.JsonFormatter

from .config import ObservabilityConfig
from .filters import HealthCheckFilter

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .pii_redaction import PIIRedactionProcessor


class _SafeFormatter(logging.Formatter):
    """Formatter that safely handles missing otelTraceID/otelSpanID on records."""

    def format(self, record: logging.LogRecord) -> str:
        record.otelTraceID = getattr(record, "otelTraceID", "")
        record.otelSpanID = getattr(record, "otelSpanID", "")
        return super().format(record)


class _OtelFormatter(JsonFormatter):
    """JSON formatter that preserves OTEL-injected trace/span IDs."""

    def add_fields(
        self,
        log_record: dict[str, object],
        record: logging.LogRecord,
        message_dict: Mapping[str, object],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        for attr in ("otelTraceID", "otelSpanID", "otelTraceFlags", "otelServiceName"):
            val = getattr(record, attr, None)
            if val is not None:
                log_record[attr] = val


class _PIIRedactionFilter(logging.Filter):
    """Scrub PII from log record messages before they reach the console."""

    def __init__(
        self,
        processor: PIIRedactionProcessor,
        name: str = "",
    ) -> None:
        super().__init__(name)
        self._processor = processor

    def filter(self, record: logging.LogRecord) -> bool:
        """Mutate record message in-place; always return True to keep the record."""
        # If the record has already been fully formatted (e.g. by a previous
        # filter/formatter pass), scrub using the pre-computed message text.
        message = record.__dict__.get("message")
        if message is not None and not record.args:
            raw = message
        else:
            try:
                raw = record.getMessage()
            except (ValueError, TypeError):
                return True
        scrubbed = self._processor.scrub_text(raw)
        if scrubbed != raw:
            record.msg = scrubbed
            record.args = None
            record.message = scrubbed
        return True


class _OtelInternalFilter(logging.Filter):
    """Block logs originating from OpenTelemetry internals.

    Prevents feedback loops where exporter failure logs re-enter the
    OTLP pipeline via the root logger's LoggingHandler.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith("opentelemetry")


def configure_logging(config: ObservabilityConfig) -> None:
    """Attach OTEL-instrumented handlers to the root logger.

    - Console handler (text or JSON depending on config).
    - PII redaction filter on console output when enabled.
    - Uvicorn health-check filter installed on uvicorn.access.
    - OTEL internal logs suppressed to prevent feedback loops.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Check if we've already configured; avoid clobbering host app's handlers
    if any(getattr(h, "_yaks_handler", False) for h in root.handlers):
        return

    # Console handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(config.log_level)
    stream_handler._yaks_handler = True  # type: ignore[attr-defined]

    if config.enable_console_json or config.environment.value == "prod":
        fmt = (
            "%(asctime)s %(levelname)s %(name)s %(message)s "
            "%(otelTraceID)s %(otelSpanID)s"
        )
        stream_handler.setFormatter(_OtelFormatter(fmt))
    else:
        fmt = (
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s | "
            "trace=%(otelTraceID)s span=%(otelSpanID)s"
        )
        stream_handler.setFormatter(_SafeFormatter(fmt))

    # Attach PII redaction to console output when enabled
    if config.enable_pii_redaction:
        # Import lazily to avoid circular dependency at module-load time
        from .pii_redaction import PIIRedactionProcessor

        processor = PIIRedactionProcessor(
            extra_safe_keys=set(config.pii_safe_keys),
        )
        stream_handler.addFilter(_PIIRedactionFilter(processor))

    root.addHandler(stream_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Prevent OTEL internal logs from reaching the root logger and
    # re-entering the OTLP pipeline (feedback-loop protection).
    otel_logger = logging.getLogger("opentelemetry")
    otel_logger.setLevel(logging.WARNING)
    otel_logger.propagate = False

    # Attach health-check filter to uvicorn.access
    uvicorn_access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, HealthCheckFilter) for f in uvicorn_access.filters):
        uvicorn_access.addFilter(HealthCheckFilter(endpoints=config.health_endpoints))

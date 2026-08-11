"""Production resilience: bounded queues, retry policies, collector resilience."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Production-hardened defaults
DEFAULT_MAX_QUEUE_SIZE = 2048
DEFAULT_MAX_EXPORT_BATCH_SIZE = 512
DEFAULT_SCHEDULE_DELAY_MS = 5000
DEFAULT_EXPORT_TIMEOUT_MS = 10000


def get_batch_processor_kwargs(
    max_queue_size: int | None = None,
    max_export_batch_size: int | None = None,
    schedule_delay_millis: int | None = None,
) -> dict[str, int]:
    """Return safe defaults for BatchSpanProcessor / BatchLogRecordProcessor.

    These bounds prevent unbounded memory growth when the collector is
    down or slow. Once the queue is full, excess spans are dropped (not
    the application).

    Args:
        max_queue_size: Override default max queue size.
        max_export_batch_size: Override default batch size.
        schedule_delay_millis: Override default schedule delay in ms.

    Returns:
        Dict of keyword arguments accepted by batch processors.
    """
    return {
        "max_queue_size": max_queue_size or DEFAULT_MAX_QUEUE_SIZE,
        "max_export_batch_size": max_export_batch_size or DEFAULT_MAX_EXPORT_BATCH_SIZE,
        "schedule_delay_millis": schedule_delay_millis or DEFAULT_SCHEDULE_DELAY_MS,
    }


def get_exporter_kwargs(timeout: int | None = None) -> dict[str, float]:
    """Return safe timeout for OTLP/HTTP exporters.

    If the collector is unreachable or slow, the export call times out
    quickly so the application thread is never blocked for long.

    Note: the OTLP/HTTP exporters (``OTLPSpanExporter``, ``OTLPLogExporter``,
    ``OTLPMetricExporter``) expect ``timeout`` in **seconds**, whereas the
    batch processors use milliseconds. This function takes the override in
    milliseconds (to stay consistent with the batch-processor API) and
    converts to seconds for the exporter.

    Args:
        timeout: Override default export timeout in milliseconds.

    Returns:
        Dict of keyword arguments accepted by OTLP exporters (``timeout``
        in seconds).
    """
    timeout_ms = timeout or DEFAULT_EXPORT_TIMEOUT_MS
    return {
        "timeout": max(1.0, timeout_ms / 1000),
    }

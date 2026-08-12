"""OpenTelemetry provider and instrumentor initialization."""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

from opentelemetry import metrics, propagate, trace
from opentelemetry.exporter.otlp.proto.http import (
    metric_exporter as otlp_metrics_http,
    trace_exporter as otlp_traces_http,
)
from opentelemetry.sdk._logs import LogRecordProcessor, LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBasedTraceIdRatio,
)
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import format_span_id, format_trace_id

from .config import ObservabilityConfig
from .instrumentors import suppress_otel_errors
from .logging_config import _OtelInternalFilter
from .pii_redaction import (
    PIIRedactionProcessor,
    RedactingLogExporter,
    RedactingSpanExporter,
)
from .resilience import get_batch_processor_kwargs, get_exporter_kwargs

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class _TraceEnrichingLogProcessor(LogRecordProcessor):
    """Copy trace_id / span_id into log attributes for APM correlation.

    Many APM backends index ``attributes.trace_id`` (not the top-level
    ``trace_id`` field) for log-to-trace correlation. This processor ensures
    both values are present.
    """

    def on_emit(
        self,
        log_record: object,
    ) -> None:  # type: ignore[override]
        """Inject trace_id / span_id as attributes on the log record."""
        lr = log_record.log_record
        if lr.trace_id and lr.trace_id != 0:
            lr.attributes["trace_id"] = format_trace_id(lr.trace_id)
        if lr.span_id and lr.span_id != 0:
            lr.attributes["span_id"] = format_span_id(lr.span_id)

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # type: ignore[override]
        return True


def _build_resource(config: ObservabilityConfig) -> Resource:
    """Build OTEL Resource with semantic conventions."""
    attrs = {
        ResourceAttributes.SERVICE_NAME: config.service_name,
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: config.environment.value,
    }
    namespace = config.service_namespace or os.getenv("OTEL_SERVICE_NAMESPACE", "")
    if namespace:
        attrs[ResourceAttributes.SERVICE_NAMESPACE] = namespace
    if config.service_version:
        attrs[ResourceAttributes.SERVICE_VERSION] = config.service_version
    if config.service_instance_id:
        attrs[ResourceAttributes.SERVICE_INSTANCE_ID] = config.service_instance_id
    attrs.update(config.extra_resource_attributes)
    return Resource.create(attrs)


def _compile_body_patterns(
    raw_patterns: tuple[str, ...],
) -> tuple[re.Pattern[str], ...]:
    compiled: list[re.Pattern[str]] = []
    for p in raw_patterns:
        try:
            compiled.append(re.compile(p))
        except re.error as exc:
            logger.warning("Invalid PII body pattern %r: %s", p, exc)
    return tuple(compiled)


def _resolve_sampler(config: ObservabilityConfig):
    """Map environment sampler config to OTEL Sampler instance."""
    sampler_name = config.sampler.lower().replace("-", "_")
    arg = float(config.sampler_arg)

    if "ratio" in sampler_name:
        return ParentBasedTraceIdRatio(arg)
    if "always_on" in sampler_name:
        return ALWAYS_ON
    if "always_off" in sampler_name:
        return ALWAYS_OFF

    # Default fallback: parent-based ratio with env arg
    return ParentBasedTraceIdRatio(arg)


def _init_tracing(
    config: ObservabilityConfig,
    resource: Resource,
) -> TracerProvider | None:
    if not config.enable_otlp_traces:
        logger.debug("OTLP traces disabled.")
        return None

    try:
        provider = _build_tracer_provider(config, resource)
        trace.set_tracer_provider(provider)
        logger.debug("Tracing initialized: endpoint=%s", config.otlp_endpoint)
        return provider
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tracing initialization failed: %s", exc)
        return None


def _build_tracer_provider(
    config: ObservabilityConfig,
    resource: Resource,
) -> TracerProvider:
    sampler = _resolve_sampler(config)
    provider = TracerProvider(resource=resource, sampler=sampler)
    exporter = _create_trace_exporter(config)
    if config.enable_pii_redaction:
        exporter = RedactingSpanExporter(
            exporter,
            PIIRedactionProcessor(
                extra_safe_keys=set(config.pii_safe_keys),
                extra_body_patterns=_compile_body_patterns(config.pii_body_patterns),
            ),
        )
    processor = _create_span_processor(exporter)
    provider.add_span_processor(processor)
    return provider


def _create_span_processor(exporter):
    from .resilience import get_batch_processor_kwargs

    kwargs = get_batch_processor_kwargs()
    return BatchSpanProcessor(
        exporter,
        max_queue_size=kwargs["max_queue_size"],
        max_export_batch_size=kwargs["max_export_batch_size"],
        schedule_delay_millis=kwargs["schedule_delay_millis"],
    )


def _create_trace_exporter(config: ObservabilityConfig):
    from .resilience import get_exporter_kwargs

    kwargs = get_exporter_kwargs()
    # Only pass endpoint explicitly when a signal-specific env var is set.
    # If omitted, the SDK auto-appends /v1/traces to OTEL_EXPORTER_OTLP_ENDPOINT.
    if config.otlp_traces_endpoint:
        kwargs["endpoint"] = config.otlp_traces_endpoint
    return otlp_traces_http.OTLPSpanExporter(**kwargs)


def _init_logging(
    config: ObservabilityConfig,
    resource: Resource,
) -> LoggerProvider | None:
    if not config.enable_otlp_logs:
        logger.debug("OTLP logs disabled.")
        return None

    try:
        provider = _create_log_provider(resource, config)
    except Exception as exc:  # noqa: BLE001
        logger.warning("OTLP logging initialization failed: %s", exc)
        return None
    else:
        logger.debug("OTLP logging initialized via LoggerProvider.")
        return provider


def _create_log_provider(
    resource: Resource,
    config: ObservabilityConfig,
) -> LoggerProvider:
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import (  # noqa: PLC2701
        OTLPLogExporter,
    )

    provider = LoggerProvider(resource=resource)
    provider.add_log_record_processor(_TraceEnrichingLogProcessor())
    exporter_kwargs = get_exporter_kwargs()
    # Only pass endpoint explicitly when a signal-specific env var is set.
    # If omitted, the SDK auto-appends /v1/logs to OTEL_EXPORTER_OTLP_ENDPOINT.
    if config.otlp_logs_endpoint:
        exporter_kwargs["endpoint"] = config.otlp_logs_endpoint
    exporter = OTLPLogExporter(**exporter_kwargs)
    if config.enable_pii_redaction:
        exporter = RedactingLogExporter(
            exporter,
            PIIRedactionProcessor(
                extra_safe_keys=set(config.pii_safe_keys),
                extra_body_patterns=_compile_body_patterns(config.pii_body_patterns),
            ),
        )
    processor = BatchLogRecordProcessor(
        exporter,
        **get_batch_processor_kwargs(),
    )

    provider.add_log_record_processor(processor)
    set_logger_provider(provider)

    # Bridge stdlib logging → OTLP via LoggingHandler on root logger.
    # Guard against duplicate handlers on repeated setup() calls.
    root = logging.getLogger()
    if any(getattr(h, "_yaks_otlp_handler", False) for h in root.handlers):
        return provider

    handler = LoggingHandler(level=config.log_level, logger_provider=provider)
    handler._yaks_otlp_handler = True  # type: ignore[attr-defined]
    # Block OTEL internal logs from re-entering the export pipeline.
    # This is the second layer of defense (the first is propagate=False
    # on the "opentelemetry" logger in configure_logging).
    handler.addFilter(_OtelInternalFilter())
    root.addHandler(handler)

    return provider


def _init_metrics(
    config: ObservabilityConfig,
    resource: Resource,
) -> MeterProvider | None:
    if not config.enable_otlp_metrics:
        logger.debug("OTLP metrics disabled.")
        return None

    try:
        provider = _build_metrics_provider(resource, config)
        metrics.set_meter_provider(provider)
        logger.debug("Metrics initialized.")
        return provider
    except Exception as exc:  # noqa: BLE001
        logger.warning("Metrics initialization failed: %s", exc)
        return None


def _build_metrics_provider(
    resource: Resource, config: ObservabilityConfig | None = None
) -> MeterProvider:
    """Build the metrics provider.

    Note: this package intentionally defines no custom instruments here.
    Metrics are produced by ``FastAPIInstrumentor`` (request duration, count,
    etc.) via auto-instrumentation; this function only wires the exporter and
    reader.
    """
    from .resilience import get_exporter_kwargs

    kwargs = get_exporter_kwargs()
    # Only pass endpoint explicitly when a signal-specific env var is set.
    # If omitted, the SDK auto-appends /v1/metrics to OTEL_EXPORTER_OTLP_ENDPOINT.
    if config is not None and config.otlp_metrics_endpoint:
        kwargs["endpoint"] = config.otlp_metrics_endpoint
    exporter = otlp_metrics_http.OTLPMetricExporter(**kwargs)
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60000)
    return MeterProvider(resource=resource, metric_readers=[reader])


class _TraceResponseMiddleware:
    """ASGI middleware that injects current trace context into response headers.

    This allows upstream callers to read the ``traceparent`` (and optionally
    B3) headers from every HTTP response, enabling downstream correlation.
    """

    def __init__(self, app) -> None:  # type: ignore[no-untyped-def]
        self.app = app

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def _send_with_trace(message):  # type: ignore[no-untyped-def]
            if message["type"] == "http.response.start":
                # Inject active span context into response headers.
                carrier: dict[str, str] = {}
                propagate.get_global_textmap().inject(carrier)
                headers = list(message.get("headers", []))
                for key, value in carrier.items():
                    headers.append((key.encode("utf-8"), value.encode("utf-8")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, _send_with_trace)


def instrument_fastapi(
    app: FastAPI,
    config: ObservabilityConfig,
) -> object | None:
    """Instrument ASGI app; return instrumentor for cleanup if needed."""
    from opentelemetry.instrumentation.fastapi import (  # noqa: PLC0415
        FastAPIInstrumentor,
    )

    # Add response trace header middleware BEFORE instrumentation so
    # returned headers are visible to callers.
    app.add_middleware(_TraceResponseMiddleware)

    try:
        excluded = ",".join(config.health_endpoints)
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls=excluded,
        )
        logger.debug("FastAPI instrumented (excluded=%s).", excluded)
        return FastAPIInstrumentor
    except Exception as exc:  # noqa: BLE001
        logger.warning("FastAPI instrumentation failed: %s", exc)
        return None


def shutdown_providers(
    trace_provider,
    log_provider,
    metric_provider,
) -> None:
    """Gracefully flush and shut down all providers on app shutdown."""
    with suppress_otel_errors():
        if trace_provider:
            trace_provider.force_flush()
            trace_provider.shutdown()
    with suppress_otel_errors():
        if log_provider:
            log_provider.force_flush(timeout_millis=5000)
            log_provider.shutdown()
    with suppress_otel_errors():
        if metric_provider:
            metric_provider.force_flush()
            metric_provider.shutdown()
    logger.info("OTEL providers shut down gracefully.")

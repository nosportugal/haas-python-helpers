"""OpenTelemetry provider and instrumentor initialization."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http import (
    metric_exporter as otlp_metrics_http,
    trace_exporter as otlp_traces_http,
)
from opentelemetry.sdk._logs import LoggerProvider
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

from .config import ObservabilityConfig
from .graceful_degradation import suppress_otel_errors
from .pii_redaction import PIIRedactionProcessor, PIIRedactingLogProcessor

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def _build_resource(config: ObservabilityConfig) -> Resource:
    """Build OTEL Resource with semantic conventions."""
    attrs = {
        ResourceAttributes.SERVICE_NAME: config.service_name,
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: config.environment.value,
    }
    if config.service_name and config.service_name != "unknown-service":
        attrs[ResourceAttributes.SERVICE_NAMESPACE] = "nos"
    attrs.update(config.extra_resource_attributes)
    return Resource.create(attrs)


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
    processor = _create_span_processor(exporter)
    provider.add_span_processor(processor)
    return provider


def _create_trace_exporter(config: ObservabilityConfig):
    return otlp_traces_http.OTLPSpanExporter(
        endpoint=f"{config.otlp_endpoint}/v1/traces",
        timeout=10,
    )


def _create_span_processor(exporter):
    return BatchSpanProcessor(
        exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        schedule_delay_millis=5000,
    )


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
        logger.debug("OTLP logging initialized.")
        return provider


def _create_log_provider(
    resource: Resource,
    config: ObservabilityConfig,
) -> LoggerProvider:
    from opentelemetry.exporter.otlp.proto.http._log_exporter import (  # noqa: PLC2701
        OTLPLogExporter,
    )
    from opentelemetry.sdk._logs import set_logger_provider  # noqa: PLC2701

    provider = LoggerProvider(resource=resource)
    exporter = OTLPLogExporter(
        endpoint=f"{config.otlp_endpoint}/v1/logs",
        timeout=10,
    )
    processor = BatchLogRecordProcessor(
        exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        schedule_delay_millis=5000,
    )
    if config.enable_pii_redaction:
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(processor, redaction)

    provider.add_log_record_processor(processor)
    try:
        set_logger_provider(provider)
    except ImportError:
        pass  # newer SDK handles it differently
    return provider


def _init_metrics(
    config: ObservabilityConfig,
    resource: Resource,
) -> MeterProvider | None:
    if not config.enable_otlp_metrics:
        logger.debug("OTLP metrics disabled.")
        return None

    try:
        exporter = otlp_metrics_http.OTLPMetricExporter(
            endpoint=f"{config.otlp_endpoint}/v1/metrics",
            timeout=10,
        )
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60000)
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        logger.debug("Metrics initialized.")
        return provider
    except Exception as exc:  # noqa: BLE001
        logger.warning("Metrics initialization failed: %s", exc)
        return None


def instrument_fastapi(
    app: FastAPI,
    config: ObservabilityConfig,
) -> object | None:
    """Instrument ASGI app; return instrumentor for cleanup if needed."""
    from opentelemetry.instrumentation.fastapi import (  # noqa: PLC0415
        FastAPIInstrumentor,
    )

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

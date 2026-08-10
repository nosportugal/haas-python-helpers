"""Behavioral tests asserting actual signal delivery through the pipeline."""

from __future__ import annotations

import logging
from unittest.mock import patch

from fastapi import FastAPI

from yaks_observability import setup
from yaks_observability.config import Environment, ObservabilityConfig


class TestOTLPLogDelivery:
    def test_logging_handler_attached_to_root(self) -> None:
        """When OTLP logs are enabled, a LoggingHandler should be on the root logger."""
        from opentelemetry.sdk._logs import LoggingHandler
        from opentelemetry.sdk.resources import Resource

        custom = ObservabilityConfig(
            environment=Environment.QA,
            service_name="test",
            service_namespace="",
            otlp_endpoint="http://localhost:4318",
            log_level="DEBUG",
            sampler="parentbased_always_on",
            sampler_arg="1.0",
            health_endpoints=("/health",),
            enable_console_json=False,
            enable_otlp_logs=True,
            enable_otlp_traces=False,
            enable_otlp_metrics=False,
            enable_pii_redaction=False,
            testing_mode=False,
        )

        resource = Resource.create({"service.name": "test"})

        root = logging.getLogger()
        # Remove any existing LoggingHandlers to avoid double counting
        for h in root.handlers[:]:
            if isinstance(h, LoggingHandler):
                root.removeHandler(h)

        from yaks_observability.instrumentation import _create_log_provider

        with patch("opentelemetry._logs.set_logger_provider"):
            provider = _create_log_provider(resource, custom)

        try:
            handler_types = [type(h).__name__ for h in root.handlers]
            assert "LoggingHandler" in handler_types, (
                f"Expected LoggingHandler in {handler_types}"
            )
        finally:
            # Clean up: remove the handler we added
            for h in root.handlers[:]:
                if isinstance(h, LoggingHandler):
                    root.removeHandler(h)
            provider.shutdown()

    def test_log_correlation_fields_injected(self) -> None:
        """LoggingInstrumentor injects otelTraceID / otelSpanID into LogRecords."""
        import io

        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry import trace

        LoggingInstrumentor().instrument(inject_trace_context=True)
        trace.set_tracer_provider(TracerProvider())
        tracer = trace.get_tracer(__name__)

        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(
            logging.Formatter("%(otelTraceID)s %(otelSpanID)s %(message)s")
        )
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        root.addHandler(handler)

        with tracer.start_as_current_span("test_span"):
            logging.getLogger("test").info("hello")

        logging.getLogger().removeHandler(handler)

        output = buf.getvalue()
        assert "hello" in output
        # otelTraceID should be non-zero (32 hex chars) inside span context
        parts = output.strip().split()
        assert len(parts) >= 2
        trace_id = parts[0]
        assert trace_id != "0" and len(trace_id) == 32


class TestPIISpanProcessor:
    def test_span_processor_receives_redaction(self) -> None:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.trace import get_tracer

        from tests._otel_helpers import InMemorySpanExporter
        from yaks_observability.pii_redaction import (
            PIIRedactionProcessor,
            RedactingSpanExporter,
        )

        inner = InMemorySpanExporter()
        exporter = RedactingSpanExporter(inner, PIIRedactionProcessor())

        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = get_tracer(__name__, tracer_provider=provider)

        with tracer.start_as_current_span("test") as span:
            span.set_attribute("user.id", "123")
            span.set_attribute("password", "secret")

        provider.force_flush()

        spans = inner.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["password"] == "[REDACTED]"
        assert spans[0].attributes["user.id"] == "123"


class TestMetricsProviderSet:
    def test_metrics_set_meter_provider_called(self) -> None:
        """When OTLP metrics enabled, set_meter_provider should be called."""
        from opentelemetry.sdk.resources import Resource

        custom = ObservabilityConfig(
            environment=Environment.QA,
            service_name="test",
            service_namespace="",
            otlp_endpoint="http://localhost:4318",
            log_level="DEBUG",
            sampler="parentbased_always_on",
            sampler_arg="1.0",
            health_endpoints=("/health",),
            enable_console_json=False,
            enable_otlp_logs=False,
            enable_otlp_traces=False,
            enable_otlp_metrics=True,
            enable_pii_redaction=False,
            testing_mode=False,
        )

        resource = Resource.create({"service.name": "test"})

        from yaks_observability.instrumentation import _build_metrics_provider

        with patch("yaks_observability.instrumentation.metrics.set_meter_provider") as mock_set:
            _build_metrics_provider(resource)

        mock_set.assert_not_called()  # _build_metrics_provider doesn't call it; _init_metrics does

        app = FastAPI()
        with patch("yaks_observability.instrumentation.metrics.set_meter_provider") as mock_set:
            with patch(
                "yaks_observability.instrumentation.otlp_metrics_http.OTLPMetricExporter",
            ):
                setup(app, config=custom)

        mock_set.assert_called_once()

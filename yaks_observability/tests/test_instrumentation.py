"""End-to-end OTEL instrumentation tests using in-memory exporters."""

from __future__ import annotations

import logging
import os
from unittest.mock import patch

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from yaks_observability import setup
from yaks_observability.config import Environment
from yaks_observability.filters import HealthCheckFilter
from tests._otel_helpers import InMemorySpanExporter


class TestTracingInMemory:
    @patch.dict(
        os.environ,
        {"ENVIRONMENT_TYPE": "testing"},
        clear=True,
    )
    def test_setup_creates_trace_provider(self) -> None:
        app = FastAPI()
        config = setup(app)
        assert config.environment == Environment.TESTING

    def test_tracing_with_inmemory_exporter(self) -> None:
        provider = TracerProvider()
        memory_exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(memory_exporter))

        # Use an explicit tracer_provider instead of the process-global one:
        # OTEL only allows set_tracer_provider() to succeed once per process,
        # so relying on the global provider makes this test order-dependent.
        tracer = trace.get_tracer(__name__, tracer_provider=provider)
        with tracer.start_as_current_span("test_operation") as span:
            span.set_attribute("test.id", "42")

        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test_operation"

    def test_health_excluded_urls(self) -> None:
        f = HealthCheckFilter(endpoints=("/health", "/ready"))
        record = _make_record("/health")
        assert f.filter(record) is False

        record = _make_record("/api/data")
        assert f.filter(record) is True


def _make_record(path: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1", "GET", path, "1.1", 200),
        exc_info=None,
    )


class TestResourceAttributes:
    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT_TYPE": "prod",
            "OTEL_SERVICE_NAME": "svc-a",
            "OTEL_SERVICE_VERSION": "9.9.9",
            "OTEL_SERVICE_INSTANCE_ID": "pod-1",
        },
        clear=True,
    )
    def test_build_resource_includes_service_identity(self) -> None:
        from yaks_observability.config import ObservabilityConfig
        from yaks_observability.instrumentation import _build_resource

        config = ObservabilityConfig.from_env()
        resource = _build_resource(config)
        assert resource.attributes["service.name"] == "svc-a"
        assert resource.attributes["service.version"] == "9.9.9"
        assert resource.attributes["service.instance.id"] == "pod-1"
        assert resource.attributes["deployment.environment"] == "prod"

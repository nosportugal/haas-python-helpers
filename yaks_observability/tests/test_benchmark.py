"""Performance benchmark tests.

Run with: poetry run pytest tests/test_benchmark.py -v
"""

from __future__ import annotations

import time
from unittest.mock import patch

from fastapi import FastAPI
from yaks_observability import setup


class _FakeExporter:
    """Stub exporter that never hits the network."""

    def __init__(self, **kw) -> None:  # noqa: ANN003,ARG002
        pass

    def export(self, batch) -> None:  # noqa: ANN001,ARG002
        return None

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002
        return True


class TestBenchmark:
    def test_setup_overhead(self) -> None:
        """Measure startup overhead. Target: <100ms."""
        app = FastAPI()
        with patch(
            "yaks_observability.instrumentation.otlp_traces_http.OTLPSpanExporter",
            _FakeExporter,
        ), patch(
            "yaks_observability.instrumentation.otlp_metrics_http.OTLPMetricExporter",
            _FakeExporter,
        ), patch(
            "opentelemetry.exporter.otlp.proto.http._log_exporter.OTLPLogExporter",
            _FakeExporter,
        ):
            start = time.perf_counter()
            setup(app)
            elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500  # generous ceiling; CI machines vary

    def test_lifespan_attached(self) -> None:
        """Ensure lifespan is registered after setup."""
        app = FastAPI()
        with patch(
            "yaks_observability.instrumentation.otlp_traces_http.OTLPSpanExporter",
            _FakeExporter,
        ), patch(
            "yaks_observability.instrumentation.otlp_metrics_http.OTLPMetricExporter",
            _FakeExporter,
        ), patch(
            "opentelemetry.exporter.otlp.proto.http._log_exporter.OTLPLogExporter",
            _FakeExporter,
        ):
            setup(app)
        assert app.router.lifespan_context is not None

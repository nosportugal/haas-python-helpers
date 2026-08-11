"""Integration tests for the main setup() function."""

from __future__ import annotations

import os
from unittest.mock import patch

from fastapi import FastAPI

from yaks_observability import setup
from yaks_observability.config import Environment, ObservabilityConfig


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


class TestSetup:
    @patch.dict(
        os.environ,
        {"ENVIRONMENT_TYPE": "testing"},
        clear=True,
    )
    def test_setup_testing_mode(self) -> None:
        app = FastAPI()
        config = setup(app)
        assert config.environment == Environment.TESTING
        assert config.testing_mode is True

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT_TYPE": "dev",
            "OTEL_SERVICE_NAME": "test-svc",
        },
        clear=True,
    )
    @patch(
        "yaks_observability.instrumentation.otlp_traces_http.OTLPSpanExporter",
        _FakeExporter,
    )
    @patch(
        "yaks_observability.instrumentation.otlp_metrics_http.OTLPMetricExporter",
        _FakeExporter,
    )
    @patch(
        "opentelemetry.exporter.otlp.proto.http._log_exporter.OTLPLogExporter",
        _FakeExporter,
    )
    def test_setup_dev_mode(self) -> None:
        app = FastAPI()
        config = setup(app)
        assert config.environment == Environment.DEV
        assert config.service_name == "test-svc"
        assert config.testing_mode is False

    @patch.dict(
        os.environ,
        {"ENVIRONMENT_TYPE": "testing"},
        clear=True,
    )
    def test_setup_with_custom_config(self) -> None:
        app = FastAPI()
        custom = ObservabilityConfig(
            environment=Environment.QA,
            service_name="custom",
            otlp_endpoint="http://custom:4318",
            log_level="ERROR",
            sampler="parentbased_always_on",
            sampler_arg="1.0",
            health_endpoints=("/health",),
            enable_console_json=True,
            enable_otlp_logs=False,
            enable_otlp_traces=False,
            enable_otlp_metrics=False,
            enable_pii_redaction=True,
            testing_mode=True,
        )
        config = setup(app, config=custom)
        assert config.environment == Environment.QA
        assert config.service_name == "custom"

    @patch.dict(
        os.environ,
        {"ENVIRONMENT_TYPE": "testing"},
        clear=True,
    )
    def test_setup_lifespan_attached(self) -> None:
        app = FastAPI()
        setup(app)
        assert app.router.lifespan_context is not None

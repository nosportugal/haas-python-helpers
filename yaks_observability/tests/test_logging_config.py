"""Tests for logging configuration."""

from __future__ import annotations

import logging

from yaks_observability.config import Environment, ObservabilityConfig
from yaks_observability.logging_config import configure_logging


class TestConfigureLogging:
    def test_dev_text_format(self) -> None:
        config = ObservabilityConfig(
            environment=Environment.DEV,
            service_name="test",
            otlp_endpoint="http://localhost:4318",
            log_level="DEBUG",
            sampler="parentbased_always_on",
            sampler_arg="1.0",
            health_endpoints=("/health",),
            enable_console_json=False,
            enable_otlp_logs=False,
            enable_otlp_traces=False,
            enable_otlp_metrics=False,
            enable_pii_redaction=True,
            testing_mode=True,
        )
        configure_logging(config)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert any(
            isinstance(h, logging.StreamHandler) for h in root.handlers
        )

    def test_prod_json_format(self) -> None:
        config = ObservabilityConfig(
            environment=Environment.PROD,
            service_name="test",
            otlp_endpoint="http://localhost:4318",
            log_level="WARN",
            sampler="parentbased_traceidratio",
            sampler_arg="0.1",
            health_endpoints=("/health",),
            enable_console_json=True,
            enable_otlp_logs=False,
            enable_otlp_traces=False,
            enable_otlp_metrics=False,
            enable_pii_redaction=True,
            testing_mode=True,
        )
        configure_logging(config)
        root = logging.getLogger()
        formatter = root.handlers[0].formatter if root.handlers else None
        assert formatter is not None

    def test_health_filter_attached(self) -> None:
        config = ObservabilityConfig(
            environment=Environment.DEV,
            service_name="test",
            otlp_endpoint="http://localhost:4318",
            log_level="DEBUG",
            sampler="parentbased_always_on",
            sampler_arg="1.0",
            health_endpoints=("/health", "/ready"),
            enable_console_json=False,
            enable_otlp_logs=False,
            enable_otlp_traces=False,
            enable_otlp_metrics=False,
            enable_pii_redaction=True,
            testing_mode=True,
        )
        configure_logging(config)
        uvicorn_access = logging.getLogger("uvicorn.access")
        assert any(
            f.__class__.__name__ == "HealthCheckFilter"
            for f in uvicorn_access.filters
        )

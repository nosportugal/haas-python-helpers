"""Tests for config module."""

from __future__ import annotations

import os
from unittest.mock import patch


from yaks_observability.config import Environment, ObservabilityConfig


class TestObservabilityConfig:
    @patch.dict(os.environ, {}, clear=True)
    def test_defaults_dev(self) -> None:
        config = ObservabilityConfig.from_env()
        assert config.environment == Environment.DEV
        assert config.log_level == "DEBUG"
        assert config.otlp_endpoint == "http://localhost:4318"
        assert config.sampler == "parentbased_always_on"
        assert config.sampler_arg == "1.0"
        assert config.testing_mode is False

    @patch.dict(os.environ, {"SERVICE_MANAGEMENT_ENVIRONMENT": "prod"}, clear=True)
    def test_prod_overrides(self) -> None:
        config = ObservabilityConfig.from_env()
        assert config.environment == Environment.PROD
        assert config.log_level == "WARN"
        assert config.sampler == "parentbased_traceidratio"
        assert config.sampler_arg == "0.1"

    @patch.dict(
        os.environ,
        {"SERVICE_MANAGEMENT_ENVIRONMENT": "testing", "OTEL_SERVICE_NAME": "test-svc"},
        clear=True,
    )
    def test_testing_mode(self) -> None:
        config = ObservabilityConfig.from_env()
        assert config.testing_mode is True
        assert config.enable_otlp_logs is False
        assert config.enable_otlp_traces is False
        assert config.enable_otlp_metrics is False

    @patch.dict(
        os.environ,
        {
            "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": "0.75",
            "LOG_LEVEL": "ERROR",
            "OTEL_HEALTH_ENDPOINTS": "/ping,/ready",
        },
        clear=True,
    )
    def test_custom_sampler_and_health(self) -> None:
        config = ObservabilityConfig.from_env()
        assert config.sampler == "parentbased_traceidratio"
        assert config.sampler_arg == "0.75"
        assert config.log_level == "ERROR"
        assert config.health_endpoints == ("/ping", "/ready")

    @patch.dict(
        os.environ,
        {"OTEL_RESOURCE_ATTRIBUTES": "k8s.pod.name=foo,deployment.color=blue"},
        clear=True,
    )
    def test_resource_attributes(self) -> None:
        config = ObservabilityConfig.from_env()
        assert config.extra_resource_attributes == {
            "k8s.pod.name": "foo",
            "deployment.color": "blue",
        }

    @patch.dict(os.environ, {"OTEL_ENABLE_PII_REDACTION": "false"}, clear=True)
    def test_pii_disabled(self) -> None:
        config = ObservabilityConfig.from_env()
        assert config.enable_pii_redaction is False

    @patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_LOGS_ENABLED": "0"}, clear=True)
    def test_bool_env_parsing_off(self) -> None:
        config = ObservabilityConfig.from_env()
        # Default env=dev, but logs explicitly disabled
        assert config.enable_otlp_logs is False

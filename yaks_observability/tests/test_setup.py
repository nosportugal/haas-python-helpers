"""Integration tests for the main setup() function."""

from __future__ import annotations

import os
from unittest.mock import patch

from fastapi import FastAPI

from yaks_observability import setup
from yaks_observability.config import Environment, ObservabilityConfig


class TestSetup:
    @patch.dict(
        os.environ,
        {"SERVICE_MANAGEMENT_ENVIRONMENT": "testing"},
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
            "SERVICE_MANAGEMENT_ENVIRONMENT": "dev",
            "OTEL_SERVICE_NAME": "test-svc",
        },
        clear=True,
    )
    def test_setup_dev_mode(self) -> None:
        app = FastAPI()
        config = setup(app)
        assert config.environment == Environment.DEV
        assert config.service_name == "test-svc"
        assert config.testing_mode is False

    @patch.dict(
        os.environ,
        {"SERVICE_MANAGEMENT_ENVIRONMENT": "testing"},
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
        {"SERVICE_MANAGEMENT_ENVIRONMENT": "testing"},
        clear=True,
    )
    def test_setup_lifespan_attached(self) -> None:
        app = FastAPI()
        setup(app)
        assert app.router.lifespan_context is not None

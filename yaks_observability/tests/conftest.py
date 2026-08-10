"""Test fixtures — offline, deterministic, in-memory."""

from __future__ import annotations

import pytest
from opentelemetry.sdk.resources import Resource

from yaks_observability.config import Environment, ObservabilityConfig


@pytest.fixture
def resource() -> Resource:
    return Resource.create({"service.name": "test"})


@pytest.fixture
def base_config() -> ObservabilityConfig:
    return ObservabilityConfig(
        environment=Environment.TESTING,
        service_name="test",
        service_namespace="",
        otlp_endpoint="",
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

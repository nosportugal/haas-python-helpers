"""Idempotency tests: repeated setup calls must not duplicate handlers."""

from __future__ import annotations

import logging
from unittest.mock import patch

from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.sdk.resources import Resource

from yaks_observability.config import Environment, ObservabilityConfig
from yaks_observability.logging_config import configure_logging


class _FakeLogExporter:
    """Stub exporter that never hits the network."""

    def export(self, records) -> None:  # noqa: ANN001,ARG002
        return None

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002
        return True


class TestConfigureLoggingIdempotency:
    def test_configure_logging_called_twice_no_duplicate_console_handler(
        self, base_config: ObservabilityConfig
    ) -> None:
        root = logging.getLogger()
        for h in root.handlers[:]:
            if getattr(h, "_yaks_handler", False):
                root.removeHandler(h)

        configure_logging(base_config)
        configure_logging(base_config)

        yaks_handlers = [
            h for h in root.handlers if getattr(h, "_yaks_handler", False)
        ]
        assert len(yaks_handlers) == 1

        for h in root.handlers[:]:
            if getattr(h, "_yaks_handler", False):
                root.removeHandler(h)


class TestOTLPLogHandlerIdempotency:
    def test_create_log_provider_called_twice_no_duplicate_otlp_handler(self) -> None:
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
        for h in root.handlers[:]:
            if isinstance(h, LoggingHandler):
                root.removeHandler(h)

        from yaks_observability.instrumentation import _create_log_provider

        try:
            with patch("opentelemetry._logs.set_logger_provider"):
                with patch(
                    "opentelemetry.exporter.otlp.proto.http._log_exporter.OTLPLogExporter",  # noqa: E501
                    return_value=_FakeLogExporter(),
                ):
                    provider1 = _create_log_provider(resource, custom)
                    provider2 = _create_log_provider(resource, custom)

            otlp_handlers = [
                h for h in root.handlers if getattr(h, "_yaks_otlp_handler", False)
            ]
            assert len(otlp_handlers) == 1
        finally:
            for h in root.handlers[:]:
                if isinstance(h, LoggingHandler):
                    root.removeHandler(h)
            provider1.shutdown()
            provider2.shutdown()

"""Regression tests for P0 blockers:

1. OTLP log feedback loop (exporter failure must not hang on recursive logs).
2. Console PII redaction (stdout must not leak PII when redaction enabled).
"""

from __future__ import annotations

import io
import logging
from unittest.mock import patch

from yaks_observability.config import Environment, ObservabilityConfig
from yaks_observability.logging_config import (
    _OtelInternalFilter,
    _PIIRedactionFilter,
    configure_logging,
)
from yaks_observability.pii_redaction import PIIRedactionProcessor
from tests._otel_helpers import InMemoryLogExporter
from opentelemetry.sdk._logs import LoggingHandler


class TestOtelInternalFilter:
    def test_blocks_opentelemetry_records(self) -> None:
        f = _OtelInternalFilter()
        record = logging.LogRecord(
            name="opentelemetry.exporter.otlp",
            level=logging.WARNING,
            pathname="",
            lineno=1,
            msg="connection failed",
            args=(),
            exc_info=None,
        )
        assert f.filter(record) is False

    def test_allows_non_otel_records(self) -> None:
        f = _OtelInternalFilter()
        record = logging.LogRecord(
            name="myapp.api",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        assert f.filter(record) is True

    def test_allows_child_with_different_prefix(self) -> None:
        f = _OtelInternalFilter()
        record = logging.LogRecord(
            name="otelcustom.logger",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        assert f.filter(record) is True


class TestPIIRedactionFilter:
    def test_scrubs_email_in_message(self) -> None:
        processor = PIIRedactionProcessor()
        f = _PIIRedactionFilter(processor)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="User email=%s confirmed",
            args=("john@nos.pt",),
            exc_info=None,
        )
        assert f.filter(record) is True
        assert "john@nos.pt" not in record.msg
        assert "[REDACTED]" in record.msg
        assert record.args is None

    def test_scrubs_token_in_message(self) -> None:
        processor = PIIRedactionProcessor()
        f = _PIIRedactionFilter(processor)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="token=%s",
            args=("abc123",),
            exc_info=None,
        )
        assert f.filter(record) is True
        assert "abc123" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_leaves_clean_messages_unchanged(self) -> None:
        processor = PIIRedactionProcessor()
        f = _PIIRedactionFilter(processor)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="status=200 ok=%s",
            args=(True,),
            exc_info=None,
        )
        assert f.filter(record) is True
        assert record.msg == "status=200 ok=%s"
        assert record.args == (True,)

    def test_survives_bad_format_string(self) -> None:
        processor = PIIRedactionProcessor()
        f = _PIIRedactionFilter(processor)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="missing %s and %s",
            args=("one",),
            exc_info=None,
        )
        # Should not raise; record left untouched on ValueError
        assert f.filter(record) is True


class TestConsolePII_Redaction:
    def test_stdout_logs_redacted_when_enabled(self) -> None:
        config = ObservabilityConfig(
            environment=Environment.PROD,
            service_name="test",
            otlp_endpoint="",
            log_level="INFO",
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
        # Remove existing yaks handlers first
        root = logging.getLogger()
        for h in root.handlers[:]:
            if getattr(h, "_yaks_handler", False):
                root.removeHandler(h)

        configure_logging(config)
        buf = io.StringIO()
        for h in root.handlers:
            if getattr(h, "_yaks_handler", False):
                # Temporarily swap the stream to capture output
                old_stream = h.stream
                h.stream = buf
                rec = logging.LogRecord(
                    name="myapp",
                    level=logging.INFO,
                    pathname="",
                    lineno=1,
                    msg="User email=%s token=%s",
                    args=("john@nos.pt", "secret123"),
                    exc_info=None,
                )
                # Use handle() to trigger handler-level filters (emit() bypasses them)
                h.handle(rec)
                h.stream = old_stream
                break

        output = buf.getvalue()
        assert "john@nos.pt" not in output, f"PII leaked in: {output}"
        assert "secret123" not in output, f"PII leaked in: {output}"
        assert "[REDACTED]" in output

        # Clean up
        for h in root.handlers[:]:
            if getattr(h, "_yaks_handler", False):
                root.removeHandler(h)


class TestOTLPFeedbackLoop:
    def test_otlp_handler_has_internal_filter(self) -> None:
        """The OTLP LoggingHandler must carry _OtelInternalFilter."""
        from opentelemetry.sdk._logs import LoggingHandler
        from opentelemetry.sdk.resources import Resource

        config = ObservabilityConfig(
            environment=Environment.QA,
            service_name="test",
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

        fake_exporter = InMemoryLogExporter()
        try:
            with patch("opentelemetry._logs.set_logger_provider"):
                with patch(
                    "opentelemetry.exporter.otlp.proto.http._log_exporter.OTLPLogExporter",
                    return_value=fake_exporter,
                ):
                    provider = _create_log_provider(resource, config)

            otlp_handlers = [
                h for h in root.handlers if getattr(h, "_yaks_otlp_handler", False)
            ]
            assert len(otlp_handlers) == 1
            filters = otlp_handlers[0].filters
            assert any(isinstance(f, _OtelInternalFilter) for f in filters), (
                f"Expected _OtelInternalFilter in {filters}"
            )
        finally:
            for h in root.handlers[:]:
                if isinstance(h, LoggingHandler):
                    root.removeHandler(h)
            provider.shutdown()

    def test_opentelemetry_logger_propagate_false(self) -> None:
        """configure_logging must set propagate=False on opentelemetry logger."""
        config = ObservabilityConfig(
            environment=Environment.PROD,
            service_name="test",
            otlp_endpoint="",
            log_level="INFO",
            sampler="parentbased_always_on",
            sampler_arg="1.0",
            health_endpoints=("/health",),
            enable_console_json=False,
            enable_otlp_logs=False,
            enable_otlp_traces=False,
            enable_otlp_metrics=False,
            enable_pii_redaction=True,
            testing_mode=False,
        )
        # Clear any existing handlers to force re-configuration
        root = logging.getLogger()
        for h in root.handlers[:]:
            if getattr(h, "_yaks_handler", False):
                root.removeHandler(h)

        configure_logging(config)
        otel = logging.getLogger("opentelemetry")
        assert otel.propagate is False

        # Clean up
        for h in root.handlers[:]:
            if getattr(h, "_yaks_handler", False):
                root.removeHandler(h)


class TestCollectorDownBoundedShutdown:
    """When the collector is unreachable, setup must not hang and must shut down
    within a bounded timeout.
    """

    def test_unreachable_collector_does_not_hang(self) -> None:
        """Using a real refused connection, the app must not block indefinitely."""
        import time

        from opentelemetry.sdk.resources import Resource

        from yaks_observability.instrumentation import _create_log_provider

        config = ObservabilityConfig(
            environment=Environment.QA,
            service_name="test",
            # RFC-863 discard port — should refuse immediately
            otlp_endpoint="http://127.0.0.1:9/v1/logs",
            log_level="INFO",
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

        start = time.monotonic()
        provider = _create_log_provider(resource, config)
        try:
            logger = logging.getLogger("test.collector")
            logger.warning("probe log for collector-down test")
            # Give the batch processor at most 10 seconds to attempt export.
            # The OTLP/HTTP exporter will retry with exponential backoff;
            # with the feedback-loop fix the total time should stay well under
            # 15 seconds even on a slow machine.
            provider.force_flush(timeout_millis=8000)
            elapsed = time.monotonic() - start
            assert elapsed < 15.0, (
                f"setup/export hung for {elapsed:.1f}s — feedback loop likely"
            )
        finally:
            for h in root.handlers[:]:
                if isinstance(h, LoggingHandler):
                    root.removeHandler(h)
            provider.shutdown()

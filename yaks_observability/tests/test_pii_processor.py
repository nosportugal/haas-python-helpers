"""Tests for the filtering exporter wrappers.

Covers RedactingSpanExporter and RedactingLogExporter.
"""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from tests._otel_helpers import InMemoryLogExporter, InMemorySpanExporter
from yaks_observability.pii_redaction import (
    PIIRedactionProcessor,
    RedactingLogExporter,
    RedactingSpanExporter,
)


class TestRedactingSpanExporter:
    def test_redacting_span_exporter_scrubs_password(self) -> None:
        inner = InMemorySpanExporter()
        exporter = RedactingSpanExporter(inner, PIIRedactionProcessor())

        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = trace.get_tracer(__name__, tracer_provider=provider)

        with tracer.start_as_current_span("test") as span:
            span.set_attribute("password", "secret")
            span.set_attribute("user.id", "123")

        provider.force_flush()

        spans = inner.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["password"] == "[REDACTED]"
        assert spans[0].attributes["user.id"] == "123"

    def test_redacting_span_exporter_delegates_other_methods(self) -> None:
        inner = InMemorySpanExporter()
        exporter = RedactingSpanExporter(inner, PIIRedactionProcessor())
        assert exporter.force_flush() is True
        exporter.shutdown()

    def test_redacting_span_exporter_default_redaction(self) -> None:
        inner = InMemorySpanExporter()
        exporter = RedactingSpanExporter(inner)

        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = trace.get_tracer(__name__, tracer_provider=provider)

        with tracer.start_as_current_span("test") as span:
            span.set_attribute("token", "abc")

        provider.force_flush()
        assert inner.get_finished_spans()[0].attributes["token"] == "[REDACTED]"

    def test_safe_keyed_otel_attrs_not_corrupted_I1(self) -> None:
        """I1 regression: safe-keyed structured attrs must pass through
        byte-identical (body scrubbing should NOT touch attribute values)."""
        from opentelemetry.exporter.otlp.proto.common.trace_encoder import (
            encode_spans,
        )

        inner = InMemorySpanExporter()
        exporter = RedactingSpanExporter(inner)

        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = trace.get_tracer(__name__, tracer_provider=provider)

        with tracer.start_as_current_span("test") as span:
            span.set_attribute(
                "url.full",
                "https://api.example.com/u?ref=US12ABCDE&next=/home&id=42",
            )
            span.set_attribute(
                "db.statement",
                "SELECT * FROM orders WHERE code='AB12CD34'",
            )
            span.set_attribute("http.target", "/health")

        provider.force_flush()
        spans = inner.get_finished_spans()
        assert len(spans) == 1
        assert b"US12ABCDE" in encode_spans(spans).SerializeToString()
        assert b"AB12CD34" in encode_spans(spans).SerializeToString()


class TestRedactingLogExporter:
    def test_redacting_log_exporter_scrubs_attributes(self) -> None:
        inner = InMemoryLogExporter()
        exporter = RedactingLogExporter(inner, PIIRedactionProcessor())

        provider = LoggerProvider(resource=Resource.create({"service.name": "t"}))
        provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
        handler = LoggingHandler(level=logging.DEBUG, logger_provider=provider)

        test_logger = logging.getLogger("test_redacting_log_exporter")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        try:
            test_logger.info("hello", extra={"password": "secret", "status": "ok"})
        finally:
            test_logger.removeHandler(handler)

        provider.force_flush()

        records = inner.get_finished_logs()
        assert len(records) == 1
        attrs = records[0].log_record.attributes
        assert attrs["password"] == "[REDACTED]"
        assert attrs["status"] == "ok"

    def test_redacting_log_exporter_scrubs_string_body(self) -> None:
        inner = InMemoryLogExporter()
        exporter = RedactingLogExporter(inner, PIIRedactionProcessor())

        provider = LoggerProvider(resource=Resource.create({"service.name": "t"}))
        provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
        handler = LoggingHandler(level=logging.DEBUG, logger_provider=provider)

        test_logger = logging.getLogger("test_redacting_log_exporter_body")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        try:
            test_logger.info("login attempt password=hunter2 ok")
        finally:
            test_logger.removeHandler(handler)

        provider.force_flush()

        records = inner.get_finished_logs()
        body = records[0].log_record.body
        assert "hunter2" not in body
        assert "[REDACTED]" in body

    def test_redacting_log_exporter_scrubs_dict_body(self) -> None:
        inner = InMemoryLogExporter()
        redaction = PIIRedactionProcessor()
        exporter = RedactingLogExporter(inner, redaction)

        provider = LoggerProvider(resource=Resource.create({"service.name": "t"}))
        provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
        otel_logger = provider.get_logger("test")

        from opentelemetry._logs import SeverityNumber
        from opentelemetry._logs._internal import LogRecord

        record = LogRecord(
            body={"password": "secret", "status": "ok"},
            severity_number=SeverityNumber.INFO,
        )
        otel_logger.emit(record)
        provider.force_flush()

        records = inner.get_finished_logs()
        body = records[0].log_record.body
        assert body["password"] == "[REDACTED]"
        assert body["status"] == "ok"

    def test_redacting_log_exporter_passes_through_non_dict_str_body(self) -> None:
        """Non-dict, non-str bodies (e.g. int) should pass through unchanged."""
        inner = InMemoryLogExporter()
        exporter = RedactingLogExporter(inner, PIIRedactionProcessor())

        provider = LoggerProvider(resource=Resource.create({"service.name": "t"}))
        provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
        otel_logger = provider.get_logger("test")

        from opentelemetry._logs import SeverityNumber
        from opentelemetry._logs._internal import LogRecord

        record = LogRecord(
            body=42,
            severity_number=SeverityNumber.INFO,
        )
        otel_logger.emit(record)
        provider.force_flush()

        records = inner.get_finished_logs()
        assert records[0].log_record.body == 42

    def test_redacting_log_exporter_delegates_other_methods(self) -> None:
        inner = InMemoryLogExporter()
        exporter = RedactingLogExporter(inner, PIIRedactionProcessor())
        assert exporter.force_flush() is True
        exporter.shutdown()


class TestRealEncoderH4:
    """Real OTLP encoder tests for events and links (H4)."""

    def test_event_attributes_redacted_on_wire(self) -> None:
        from opentelemetry.exporter.otlp.proto.common.trace_encoder import (
            encode_spans,
        )

        inner = InMemorySpanExporter()
        exporter = RedactingSpanExporter(inner, PIIRedactionProcessor())

        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = trace.get_tracer(__name__, tracer_provider=provider)

        with tracer.start_as_current_span("test") as span:
            span.add_event("login", {"password": "secret", "status": "ok"})

        provider.force_flush()
        spans = inner.get_finished_spans()
        assert len(spans) == 1

        # real OTLP encode must succeed and secrets must be redacted
        proto = encode_spans(spans)
        payload = proto.SerializeToString()
        assert b"secret" not in payload
        assert b"[REDACTED]" in payload
        assert b"ok" in payload

    def test_link_attributes_redacted_on_wire(self) -> None:
        from opentelemetry.exporter.otlp.proto.common.trace_encoder import (
            encode_spans,
        )

        inner = InMemorySpanExporter()
        exporter = RedactingSpanExporter(inner, PIIRedactionProcessor())

        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = trace.get_tracer(__name__, tracer_provider=provider)

        with tracer.start_as_current_span("parent") as parent:
            ctx = parent.get_span_context()
            link = trace.Link(ctx, {"password": "secret", "status": "ok"})
            with tracer.start_as_current_span(
                "child",
                links=[link],
            ) as child:
                child.set_attribute("user.id", "123")

        provider.force_flush()
        spans = inner.get_finished_spans()
        assert len(spans) == 2

        # Find child span
        child_span = next(s for s in spans if s.name == "child")
        proto = encode_spans([child_span])
        payload = proto.SerializeToString()
        assert b"secret" not in payload
        assert b"[REDACTED]" in payload
        assert b"ok" in payload

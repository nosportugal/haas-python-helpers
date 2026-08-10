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

    def test_redacting_log_exporter_delegates_other_methods(self) -> None:
        inner = InMemoryLogExporter()
        exporter = RedactingLogExporter(inner, PIIRedactionProcessor())
        assert exporter.force_flush() is True
        exporter.shutdown()

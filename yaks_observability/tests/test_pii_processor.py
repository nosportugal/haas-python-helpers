"""Tests for PIIRedactingLogProcessor covering on_emit/shutdown/force_flush."""

from __future__ import annotations

from unittest.mock import MagicMock

from yaks_observability.pii_redaction import (
    PIIRedactionProcessor,
    PIIRedactingLogProcessor,
    PIIRedactingSpanProcessor,
)


class MockLogRecord:
    def __init__(self, attributes: dict | None = None) -> None:
        self.attributes = attributes


class MockLogData:
    def __init__(self, attributes: dict | None = None) -> None:
        self.log_record = MockLogRecord(attributes)


class TestPIIRedactingLogProcessor:
    def test_on_emit_scrubs_attributes(self) -> None:
        inner = MagicMock()
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        log_data = MockLogData({"password": "secret", "status": "ok"})
        processor.on_emit(log_data)
        assert log_data.log_record.attributes["password"] == "[REDACTED]"
        assert log_data.log_record.attributes["status"] == "ok"
        inner.on_emit.assert_called_once_with(log_data)

    def test_on_emit_no_attributes(self) -> None:
        inner = MagicMock()
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        log_data = MockLogData(None)
        processor.on_emit(log_data)
        inner.on_emit.assert_called_once_with(log_data)

    def test_on_emit_no_log_record(self) -> None:
        inner = MagicMock()
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        log_data = MagicMock()
        del log_data.log_record  # force AttributeError path
        processor.on_emit(log_data)
        inner.on_emit.assert_called_once_with(log_data)

    def test_shutdown(self) -> None:
        inner = MagicMock()
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        processor.shutdown()
        inner.shutdown.assert_called_once()

    def test_force_flush(self) -> None:
        inner = MagicMock()
        inner.force_flush.return_value = True
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        result = processor.force_flush(timeout_millis=500)
        assert result is True
        inner.force_flush.assert_called_once_with(500)


class TestPIIRedactingSpanProcessor:
    def test_on_end_scrubs_attributes(self) -> None:
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingSpanProcessor(redaction)
        span = MagicMock()
        span.attributes = {"password": "secret", "status": "ok"}
        processor.on_end(span)
        assert span.attributes["password"] == "[REDACTED]"
        assert span.attributes["status"] == "ok"

    def test_on_end_no_attributes(self) -> None:
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingSpanProcessor(redaction)
        span = MagicMock()
        del span.attributes
        processor.on_end(span)

"""Tests for PIIRedactingLogProcessor covering emit/shutdown/force_flush."""

from __future__ import annotations

from unittest.mock import MagicMock

from yaks_observability.pii_redaction import (
    PIIRedactionProcessor,
    PIIRedactingLogProcessor,
)


class MockLogRecord:
    def __init__(self, attributes: dict | None = None) -> None:
        self.attributes = attributes


class MockLogData:
    def __init__(self, attributes: dict | None = None) -> None:
        self.log_record = MockLogRecord(attributes)


class TestPIIRedactingLogProcessor:
    def test_emit_scrubs_attributes(self) -> None:
        inner = MagicMock()
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        log_data = MockLogData({"password": "secret", "status": "ok"})
        processor.emit(log_data)
        assert log_data.log_record.attributes["password"] == "[REDACTED]"
        assert log_data.log_record.attributes["status"] == "ok"
        inner.emit.assert_called_once_with(log_data)

    def test_emit_no_attributes(self) -> None:
        inner = MagicMock()
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        log_data = MockLogData(None)
        processor.emit(log_data)
        inner.emit.assert_called_once_with(log_data)

    def test_emit_no_log_record(self) -> None:
        inner = MagicMock()
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        log_data = MagicMock()
        del log_data.log_record  # force AttributeError path
        processor.emit(log_data)
        inner.emit.assert_called_once_with(log_data)

    def test_emit_delegates_force_flush(self) -> None:
        inner = MagicMock()
        inner.emit = None  # type: ignore[assignment]
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        log_data = MockLogData(None)
        processor.emit(log_data)
        inner.force_flush.assert_called_once()

    def test_shutdown(self) -> None:
        inner = MagicMock()
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        processor.shutdown()
        inner.shutdown.assert_called_once()

    def test_shutdown_noop(self) -> None:
        inner = MagicMock()
        del inner.shutdown
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        processor.shutdown()

    def test_force_flush(self) -> None:
        inner = MagicMock()
        inner.force_flush.return_value = True
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        result = processor.force_flush(timeout_millis=500)
        assert result is True
        inner.force_flush.assert_called_once_with(500)

    def test_force_flush_noop(self) -> None:
        inner = MagicMock()
        del inner.force_flush
        redaction = PIIRedactionProcessor()
        processor = PIIRedactingLogProcessor(inner, redaction)
        result = processor.force_flush(timeout_millis=500)
        assert result is True

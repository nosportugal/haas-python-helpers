"""Test helpers for OpenTelemetry SDK 1.44+ compatibility."""

from __future__ import annotations

from opentelemetry.sdk._logs.export import (
    LogRecordExporter,
    LogRecordExportResult,
)
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)


class InMemorySpanExporter(SpanExporter):
    """In-memory span exporter for testing.

    SDK 1.44.0 removed the built-in InMemorySpanExporter; this minimal
    reimplementation is provided for test isolation.
    """

    def __init__(self) -> None:
        self._spans: list[object] = []

    def export(self, spans) -> SpanExportResult:
        self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def get_finished_spans(self) -> list[object]:
        return self._spans.copy()

    def clear(self) -> None:
        self._spans.clear()

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002
        return True


class InMemoryLogExporter(LogRecordExporter):
    """In-memory log record exporter for testing (network-free)."""

    def __init__(self) -> None:
        self._logs: list[object] = []

    def export(self, batch) -> LogRecordExportResult:
        self._logs.extend(batch)
        return LogRecordExportResult.SUCCESS

    def get_finished_logs(self) -> list[object]:
        return self._logs.copy()

    def clear(self) -> None:
        self._logs.clear()

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002
        return True

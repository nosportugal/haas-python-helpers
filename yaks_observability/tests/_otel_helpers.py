"""Test helpers for OpenTelemetry SDK 1.44+ compatibility."""

from __future__ import annotations

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

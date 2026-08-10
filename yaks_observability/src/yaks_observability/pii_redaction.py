"""PII / sensitive-field redaction before OTLP export.

Allow-list safe: unknown fields are scrubbed by default unless explicitly marked safe.
This prevents accidental PII leakage when new fields are added.

Real OTEL SDK objects (``ReadableSpan.attributes`` is a read-only ``mappingproxy``;
``LogRecord.attributes`` is a ``BoundedAttributes`` instance) do not allow attribute
mutation. Redaction is therefore implemented as filtering exporter wrappers that
substitute lightweight, mutable-attribute copies of the span/log record before
delegating to the real exporter.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from opentelemetry.sdk._logs.export import LogRecordExporter, LogRecordExportResult
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

if TYPE_CHECKING:
    from collections.abc import Sequence

    from opentelemetry.sdk._logs import ReadableLogRecord
    from opentelemetry.sdk.trace import ReadableSpan


# Sensitive field patterns — substring match for near-zero false positives.
# Standalone "auth" is omitted to avoid over-redacting "author" etc.
_SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"api[_\-]?key", re.IGNORECASE),
    re.compile(r"authorization", re.IGNORECASE),
    re.compile(r"cookie", re.IGNORECASE),
    re.compile(r"session", re.IGNORECASE),
    re.compile(r"email", re.IGNORECASE),
    re.compile(r"phone", re.IGNORECASE),
    re.compile(r"ssn", re.IGNORECASE),
    re.compile(r"credit[_\-]?card", re.IGNORECASE),
    re.compile(r"cvv", re.IGNORECASE),
    re.compile(r"iban", re.IGNORECASE),
)

# Patterns used to scrub sensitive values embedded within free-text log bodies,
# e.g. "password=hunter2" or "token: abc123".
_BODY_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(
        rf"({p.pattern})([\"']?\s*[:=]\s*[\"']?)([^\s,;\"']+)",
        re.IGNORECASE,
    )
    for p in _SENSITIVE_PATTERNS
)

_REDACTED = "[REDACTED]"


class PIIRedactionProcessor:
    """Scrub sensitive keys from log attributes / trace attributes."""

    def __init__(self, extra_safe_keys: set[str] | None = None) -> None:
        self.safe_keys: set[str] = set(extra_safe_keys or ())

    def is_safe(self, key: str) -> bool:
        if key in self.safe_keys:
            return True
        return not any(p.search(key) for p in _SENSITIVE_PATTERNS)

    def scrub_dict(self, data: dict) -> dict:
        """Return a deep copy with sensitive keys redacted recursively."""
        result: dict = {}
        for k, v in data.items():
            if not self.is_safe(k):
                result[k] = _REDACTED
            elif isinstance(v, dict):
                result[k] = self.scrub_dict(v)
            elif isinstance(v, list):
                result[k] = [
                    self.scrub_dict(item) if isinstance(item, dict) else item
                    for item in v
                ]
            else:
                result[k] = v
        return result

    def scrub_value(self, key: str, value: object) -> object:
        return value if self.is_safe(key) else _REDACTED

    @staticmethod
    def scrub_text(text: str) -> str:
        """Redact sensitive "key=value"/"key: value" fragments in free text."""
        scrubbed = text
        for pattern in _BODY_VALUE_PATTERNS:
            scrubbed = pattern.sub(rf"\1\2{_REDACTED}", scrubbed)
        return scrubbed


class _RedactedAttributesProxy:
    """Delegates all attribute access to ``wrapped`` except for ``overrides``."""

    def __init__(self, wrapped: Any, **overrides: Any) -> None:
        object.__setattr__(self, "_wrapped", wrapped)
        object.__setattr__(self, "_overrides", overrides)

    def __getattr__(self, name: str) -> Any:
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            return overrides[name]
        return getattr(object.__getattribute__(self, "_wrapped"), name)


class RedactingSpanExporter(SpanExporter):
    """Wraps a ``SpanExporter`` and redacts PII from span attributes on export."""

    def __init__(
        self,
        exporter: SpanExporter,
        redaction: PIIRedactionProcessor | None = None,
    ) -> None:
        self._exporter = exporter
        self._redaction = redaction or PIIRedactionProcessor()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        redacted_spans = [
            _RedactedAttributesProxy(
                span,
                attributes=self._redaction.scrub_dict(dict(span.attributes or {})),
            )
            for span in spans
        ]
        return self._exporter.export(redacted_spans)

    def shutdown(self) -> None:
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._exporter.force_flush(timeout_millis)


class RedactingLogExporter(LogRecordExporter):
    """Wraps a ``LogRecordExporter`` and redacts PII from log records on export."""

    def __init__(
        self,
        exporter: LogRecordExporter,
        redaction: PIIRedactionProcessor | None = None,
    ) -> None:
        self._exporter = exporter
        self._redaction = redaction or PIIRedactionProcessor()

    def export(self, batch: Sequence[ReadableLogRecord]) -> LogRecordExportResult:
        redacted_batch = [self._redact_record(record) for record in batch]
        return self._exporter.export(redacted_batch)

    def _redact_record(self, record: ReadableLogRecord) -> ReadableLogRecord:
        log_record = record.log_record
        attrs = dict(log_record.attributes or {})
        redacted_attrs = self._redaction.scrub_dict(attrs)

        body = log_record.body
        if isinstance(body, dict):
            redacted_body: Any = self._redaction.scrub_dict(body)
        elif isinstance(body, str):
            redacted_body = self._redaction.scrub_text(body)
        else:
            redacted_body = body

        redacted_log_record = _RedactedAttributesProxy(
            log_record,
            attributes=redacted_attrs,
            body=redacted_body,
        )
        return _RedactedAttributesProxy(record, log_record=redacted_log_record)

    def shutdown(self) -> None:
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._exporter.force_flush(timeout_millis)

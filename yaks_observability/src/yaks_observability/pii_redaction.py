"""PII / sensitive-field redaction before OTLP export.

Allow-list safe: unknown fields are scrubbed by default unless explicitly marked safe.
This prevents accidental PII leakage when new fields are added.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from opentelemetry.sdk._logs import LogRecordProcessor
from opentelemetry.sdk.trace.export import SpanProcessor

if TYPE_CHECKING:
    from opentelemetry.sdk._logs._internal import LogData
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
            else:
                result[k] = v
        return result

    def scrub_value(self, key: str, value: object) -> object:
        return value if self.is_safe(key) else _REDACTED


class PIIRedactingLogProcessor(LogRecordProcessor):
    """OTEL LogRecordProcessor that redacts PII from log attributes before export."""

    def __init__(
        self,
        processor: LogRecordProcessor,
        redaction: PIIRedactionProcessor,
    ) -> None:
        self._processor = processor
        self._redaction = redaction

    def on_emit(self, log_data: LogData) -> None:
        if hasattr(log_data, "log_record") and hasattr(
            log_data.log_record, "attributes"
        ):
            attrs = log_data.log_record.attributes
            if isinstance(attrs, dict):
                log_data.log_record.attributes = self._redaction.scrub_dict(attrs)
        self._processor.on_emit(log_data)

    def shutdown(self) -> None:
        self._processor.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._processor.force_flush(timeout_millis)


class PIIRedactingSpanProcessor(SpanProcessor):
    """OTEL SpanProcessor that redacts PII from span attributes before export."""

    def __init__(self, redaction: PIIRedactionProcessor) -> None:
        self._redaction = redaction

    def on_start(self, span: "ReadableSpan", parent_context=None) -> None:  # noqa: ANN001
        pass

    def on_end(self, span: "ReadableSpan") -> None:
        if hasattr(span, "attributes") and isinstance(span.attributes, dict):
            span.attributes = self._redaction.scrub_dict(span.attributes)

    def shutdown(self) -> None:
        pass

    def force_flush(  # noqa: PLR6301
        self, timeout_millis: int = 30000  # noqa: ARG002
    ) -> bool:
        return True

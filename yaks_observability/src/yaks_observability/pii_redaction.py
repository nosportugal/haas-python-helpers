"""PII / sensitive-field redaction before OTLP export.

Deny-list semantics: fields that match known PII key terms or value patterns are
scrubbed to ``[REDACTED]``; everything else passes through unchanged. This is the
pragmatic choice for OTEL because an exhaustive allow-list would require tracking
all semantic convention attributes across evolving OTEL specs.

Real OTEL SDK objects (``ReadableSpan.attributes`` is a read-only ``mappingproxy``;
``LogRecord.attributes`` is a ``BoundedAttributes`` instance) do not allow attribute
mutation. Redaction is therefore implemented as filtering exporter wrappers that
substitute lightweight, mutable-attribute copies of the span/log record before
delegating to the real exporter.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from opentelemetry.sdk._logs.export import (
    LogRecordExporter,
    LogRecordExportResult,
)
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

if TYPE_CHECKING:
    from collections.abc import Sequence

    from opentelemetry.sdk._logs import ReadableLogRecord
    from opentelemetry.sdk.trace import ReadableSpan

_REDACTED = "[REDACTED]"

# ---------------------------------------------------------------------------
# 1. Static key-name patterns (alpha-boundary match)
# ---------------------------------------------------------------------------
# Standalone "auth" is included but guarded by alpha-boundary checks so
# "author" is NOT redacted while "auth" and "authorization" are.
# The default _BUILT_IN_SAFE_KEYS below protect common non-secret fields;
# callers can extend via PIIRedactionProcessor(extra_safe_keys=..., ...).

_SENSITIVE_KEY_TERMS: tuple[str, ...] = (
    "auth",
    "authorization",
    "password",
    "secret",
    "api[_\\-]?key",
    "cookie",
    "phone",
    "ssn",
    "credit[_\\-]?card",
    "cvv",
    "session",
    "email",
    "iban",
    "token",
    "access[_\\-]?token",
    "refresh[_\\-]?token",
    "id[_\\-]?token",
    "first[_\\-]?name",
    "last[_\\-]?name",
    "full[_\\-]?name",
    "user[_\\-]?name",
    "street[_\\-]?address",
    "home[_\\-]?address",
    "billing[_\\-]?address",
    "postal[_\\-]?address",
    "dob",
    "ip[_\\-]?address",
    "nif",
    "national[_\\-]?id",
    "passport",
)

# Alpha-boundary guards (not \b word-boundary) so that keys like
# "auth_token" still match "token", while "prompt_tokens" does not.
_SENSITIVE_KEY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"(?<![a-zA-Z]){t}(?![a-zA-Z])", re.IGNORECASE)
    for t in _SENSITIVE_KEY_TERMS
)

# Built-in keys that are safe by default (prevents over-redaction of
# common non-secret observability fields).
_BUILT_IN_SAFE_KEYS: frozenset[str] = frozenset({
    "prompt_tokens",
    "completion_tokens",
    "token_count",
    "session_duration",
    "session_start",
    "session_id",
    "email_verified",
    "token_type",
    "service_name",
    "server.address",
    "client.address",
    "network.peer.address",
    "network.local.address",
    "source.address",
    "destination.address",
})

# ---------------------------------------------------------------------------
# 2. Body text scrubbing – value-shape patterns + key-value patterns
# ---------------------------------------------------------------------------

# Patterns that match sensitive *values* regardless of a preceding key.
# These catch bare secrets in free text (e-mails, PANs, IBANs, JWTs).
_BODY_SHAPE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # E-mail addresses
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    # Credit-card-like numbers (16 digits, grouped or ungrouped)
    re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    # IBAN (simplified: 2 letters + 2 digits + 13-30 alphanum)
    re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,28}\b"),
    # JWTs  (eyJ… base64url segments)
    re.compile(r"\beyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b"),
    # Bearer tokens after colon/space (JWT or opaque)
    re.compile(
        r"\b([Bb]earer)\s*[:=]\s+([^,;\s]+)",
        re.IGNORECASE,
    ),
)

# ---------------------------------------------------------------------------
# 3. Key-value patterns (JSON first, then plain KVP)
# ---------------------------------------------------------------------------

_QC_DQ = chr(34)  # "
_QC_SQ = chr(39)  # '
_QC_BOTH = _QC_DQ + _QC_SQ

# JSON double-quoted:  "key": "string"  |  "key": number/literal
_JSON_BODY_KVP_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(
        rf"[{_QC_DQ}]({t})[{_QC_DQ}]\s*:\s*(?:"
        rf"[{_QC_DQ}][^{_QC_DQ}\r\n]*?[{_QC_DQ}]|"
        rf"(?:null|true|false|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
        rf")",
        re.IGNORECASE,
    )
    for t in _SENSITIVE_KEY_TERMS
)

# JSON single-quoted:  'key': 'string'  |  'key': number/literal
_JSON_SQ_BODY_KVP_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(
        rf"[{_QC_SQ}]({t})[{_QC_SQ}]\s*:\s*(?:"
        rf"[{_QC_SQ}][^{_QC_SQ}\r\n]*?[{_QC_SQ}]|"
        rf"(?:null|true|false|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
        rf")",
        re.IGNORECASE,
    )
    for t in _SENSITIVE_KEY_TERMS
)

# Plain KVP: key=value, key: value, key="value", key='value'.
# Negative lookbehind ensures we do NOT match quoted JSON keys.
# Value extends up to structural boundary (comma, semicolon, ampersand,
# brace, bracket, line-break, or EOL) so multi-word values are not truncated.
_PLAIN_BODY_KVP_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(
        rf"(?<![{_QC_BOTH}])(\b{t}\b)(\s*+[:=]\s*+)"
        rf"(?:[{_QC_BOTH}]?)(?!\[REDACTED\])(.+?)(?:[{_QC_BOTH}]?)"
        rf"(?=[,;&{{}}\[\]\r\n]|$)",
        re.IGNORECASE,
    )
    for t in _SENSITIVE_KEY_TERMS
)


class PIIRedactionProcessor:
    """Scrub sensitive keys from log attributes / trace attributes.

    Args:
        extra_safe_keys: additional keys that should never be redacted.
        extra_body_patterns: additional regexes matched against string log
            bodies (shape patterns, e.g. company-specific ID formats).
    """

    def __init__(
        self,
        extra_safe_keys: set[str] | None = None,
        extra_body_patterns: tuple[re.Pattern[str], ...] | None = None,
    ) -> None:
        self.safe_keys: set[str] = set(extra_safe_keys or ())

        # Explicitly track pattern kinds so user-provided shape patterns are
        # never mis-routed as KVP patterns, regardless of group count (I2).
        self._shape_patterns: tuple[re.Pattern[str], ...] = (
            *_BODY_SHAPE_PATTERNS,
            *(extra_body_patterns or ()),
        )
        # Store JSON / plain KVP patterns separately so each gets the right
        # replacement string (preserving its own quote style).
        self._json_dq_patterns: tuple[re.Pattern[str], ...] = _JSON_BODY_KVP_PATTERNS
        self._json_sq_patterns: tuple[re.Pattern[str], ...] = _JSON_SQ_BODY_KVP_PATTERNS
        self._plain_kvp_patterns: tuple[re.Pattern[str], ...] = _PLAIN_BODY_KVP_PATTERNS

    def is_safe(self, key: str) -> bool:
        if key in _BUILT_IN_SAFE_KEYS:
            return True
        if key in self.safe_keys:
            return True
        return not any(p.search(key) for p in _SENSITIVE_KEY_PATTERNS)

    def scrub_dict(self, data: dict, scrub_strings: bool = False) -> dict:
        """Return a deep copy with sensitive keys redacted recursively.

        Args:
            data: mapping to scrub.
            scrub_strings: if ``True``, string values are also run through
                :meth:`scrub_text` so that PII embedded inside dict values
                (e.g. ``{"msg": "token=abc"}``) is caught.
                Defaults to ``False`` so that structured span/log attributes
                are redacted by KEY only, avoiding false positives (I1).
        """
        result: dict = {}
        for k, v in data.items():
            if not self.is_safe(k):
                result[k] = _REDACTED
            elif isinstance(v, dict):
                result[k] = self.scrub_dict(v, scrub_strings=scrub_strings)
            elif isinstance(v, list):
                result[k] = [
                    (
                        self.scrub_dict(item, scrub_strings=scrub_strings)
                        if isinstance(item, dict)
                        else (
                            self.scrub_text(item)
                            if scrub_strings and isinstance(item, str)
                            else item
                        )
                    )
                    for item in v
                ]
            elif scrub_strings and isinstance(v, str):
                result[k] = self.scrub_text(v)
            else:
                result[k] = v
        return result

    def scrub_value(self, key: str, value: object) -> object:
        return value if self.is_safe(key) else _REDACTED

    def scrub_text(self, text: str) -> str:
        """Redact sensitive values in free text.

        Order matters for idempotency: structural key-value patterns run
        FIRST (JSON, then plain KVP) so that key-based redaction consumes
        sensitive values before the value-shape patterns run.  If shape
        patterns ran first they would leave bare ``[REDACTED]`` placeholders
        that the KVP patterns would then re-wrap, producing doubled or
        mangled placeholders (e.g. ``[REDACTED][REDACTED]``).

        JSON KVP patterns replace the entire key-value expression while
        preserving the quote style of the key.  Plain KVP patterns preserve
        the key and delimiter while redacting only the value.  Shape patterns
        (value-only, no key) then catch any remaining bare secrets.

        Performance note: this iterates pre-compiled regexes over the
        input once. It is only called on log message *bodies* (free text);
        structured span/log attributes default to key-only redaction via
        :meth:`scrub_dict` so this hot path is not hit for every attribute.
        """
        scrubbed = text
        # JSON double-quote: key: "string"
        for pattern in self._json_dq_patterns:
            scrubbed = pattern.sub(rf'"\g<1>": "{_REDACTED}"', scrubbed)
        # JSON single-quote: 'key': 'string'
        for pattern in self._json_sq_patterns:
            scrubbed = pattern.sub(rf"'\g<1>': '{_REDACTED}'", scrubbed)
        # Plain KVP patterns → preserve key+delimiter, redact value
        for pattern in self._plain_kvp_patterns:
            scrubbed = pattern.sub(rf"\1\2{_REDACTED}", scrubbed)
        # Shape patterns → whole-match redaction of any remaining bare secrets
        for pattern in self._shape_patterns:
            scrubbed = pattern.sub(_REDACTED, scrubbed)
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
        return getattr(
            object.__getattribute__(self, "_wrapped"),
            name,
        )


class _RedactedEventProxy:
    """Proxy an OTEL ``Event`` with redacted attributes."""

    def __init__(
        self,
        wrapped: Any,
        attributes: dict[str, Any],
    ) -> None:
        object.__setattr__(self, "_wrapped", wrapped)
        object.__setattr__(self, "_attrs", attributes)

    def __getattr__(self, name: str) -> Any:
        if name == "attributes":
            return object.__getattribute__(self, "_attrs")
        return getattr(
            object.__getattribute__(self, "_wrapped"),
            name,
        )


class _RedactedLinkProxy:
    """Proxy an OTEL ``Link`` with redacted attributes."""

    def __init__(
        self,
        wrapped: Any,
        attributes: dict[str, Any],
    ) -> None:
        object.__setattr__(self, "_wrapped", wrapped)
        object.__setattr__(self, "_attrs", attributes)

    def __getattr__(self, name: str) -> Any:
        if name == "attributes":
            return object.__getattribute__(self, "_attrs")
        return getattr(
            object.__getattribute__(self, "_wrapped"),
            name,
        )


class RedactingSpanExporter(SpanExporter):
    """Wraps a ``SpanExporter`` and redacts PII from span attributes on export."""

    def __init__(
        self,
        exporter: SpanExporter,
        redaction: PIIRedactionProcessor | None = None,
    ) -> None:
        self._exporter = exporter
        self._redaction = redaction or PIIRedactionProcessor()

    def _scrub_events(self, span: ReadableSpan) -> tuple:
        result = []
        for ev in span.events or ():
            redacted_attrs = self._redaction.scrub_dict(dict(ev.attributes or {}))
            result.append(_RedactedEventProxy(ev, attributes=redacted_attrs))
        return tuple(result)

    def _scrub_links(self, span: ReadableSpan) -> tuple:
        result = []
        for link in span.links or ():
            redacted_attrs = self._redaction.scrub_dict(dict(link.attributes or {}))
            result.append(_RedactedLinkProxy(link, attributes=redacted_attrs))
        return tuple(result)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        redacted_spans = []
        for span in spans:
            redacted = _RedactedAttributesProxy(
                span,
                attributes=self._redaction.scrub_dict(dict(span.attributes or {})),
                events=self._scrub_events(span),
                links=self._scrub_links(span),
            )
            redacted_spans.append(redacted)
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
        # Structured attributes: redact by key only (I1)
        redacted_attrs = self._redaction.scrub_dict(attrs, scrub_strings=False)

        body = log_record.body
        if isinstance(body, dict):
            # Log body dicts may contain free-text string values; deep-scrub them
            redacted_body: Any = self._redaction.scrub_dict(body, scrub_strings=True)
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

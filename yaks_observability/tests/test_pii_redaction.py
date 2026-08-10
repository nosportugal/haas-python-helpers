"""Tests for PII redaction."""

from __future__ import annotations

from yaks_observability.pii_redaction import PIIRedactionProcessor


class TestPIIRedactionProcessor:
    def test_password_redacted(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("password", "secret123") == "[REDACTED]"
        assert r.scrub_value("userPassword", "x") == "[REDACTED]"

    def test_token_redacted(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("accessToken", "tok") == "[REDACTED]"
        assert r.scrub_value("token", "tok") == "[REDACTED]"

    def test_safe_fields_preserved(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("status", "ok") == "ok"
        assert r.scrub_value("service_name", "foo") == "foo"

    def test_extra_safe_keys(self) -> None:
        r = PIIRedactionProcessor(extra_safe_keys={"my_token"})
        assert r.scrub_value("my_token", "visible") == "visible"
        assert r.scrub_value("other_token", "hidden") == "[REDACTED]"

    def test_scrub_dict(self) -> None:
        r = PIIRedactionProcessor()
        data = {"service": "foo", "password": "bar", "status": 200}
        result = r.scrub_dict(data)
        assert result["service"] == "foo"
        assert result["password"] == "[REDACTED]"
        assert result["status"] == 200

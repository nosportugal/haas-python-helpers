"""Tests for PII redaction."""

from __future__ import annotations

import re

from yaks_observability.pii_redaction import PIIRedactionProcessor


class TestPIIRedactionProcessor:
    REDACTED = "[REDACTED]"

    def test_password_redacted(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("password", "secret123") == self.REDACTED
        assert r.scrub_value("new_password", "x") == self.REDACTED

    def test_token_redacted(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("accessToken", "tok") == self.REDACTED
        assert r.scrub_value("token", "tok") == self.REDACTED

    def test_safe_fields_preserved(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("status", "ok") == "ok"
        assert r.scrub_value("service_name", "foo") == "foo"

    def test_extra_safe_keys(self) -> None:
        r = PIIRedactionProcessor(extra_safe_keys={"my_token"})
        assert r.scrub_value("my_token", "visible") == "visible"
        assert r.scrub_value("other_token", "hidden") == self.REDACTED

    def test_scrub_dict(self) -> None:
        r = PIIRedactionProcessor()
        data = {"service": "foo", "password": "bar", "status": 200}
        result = r.scrub_dict(data)
        assert result["service"] == "foo"
        assert result["password"] == self.REDACTED
        assert result["status"] == 200

    def test_recursive_scrub(self) -> None:
        r = PIIRedactionProcessor()
        data = {
            "service": "foo",
            "nested": {"password": "secret", "status": 200},
            "flat": "ok",
        }
        result = r.scrub_dict(data)
        assert result["service"] == "foo"
        assert result["nested"]["password"] == self.REDACTED
        assert result["nested"]["status"] == 200
        assert result["flat"] == "ok"

    def test_word_boundary_author_not_redacted(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("author", "Jane") == "Jane"
        assert r.scrub_value("session_id", "abc") == "abc"
        assert r.scrub_value("authorization", "bear") == self.REDACTED

    def test_scrub_dict_recurses_into_lists(self) -> None:
        r = PIIRedactionProcessor()
        data = {
            "service": "foo",
            "users": [
                {"email": "a@b.com", "status": "active"},
                {"email": "c@d.com", "status": "inactive"},
            ],
            "tags": ["ok", "fine"],
        }
        result = r.scrub_dict(data)
        assert result["service"] == "foo"
        assert result["users"][0]["email"] == self.REDACTED
        assert result["users"][0]["status"] == "active"
        assert result["users"][1]["email"] == self.REDACTED
        assert result["tags"] == ["ok", "fine"]

    # ------------------------------------------------------------------
    # H1: scrub_text now uses instance patterns (shape + KVP)
    # ------------------------------------------------------------------

    def test_scrub_text_instance_body_patterns(self) -> None:
        r = PIIRedactionProcessor(extra_body_patterns=(re.compile(r"\bCUST-\d+\b"),))
        text = "order CUST-12345 confirmed"
        result = r.scrub_text(text)
        assert "CUST-12345" not in result
        assert self.REDACTED in result
        # without custom pattern, it should not redact
        r2 = PIIRedactionProcessor()
        assert "CUST-12345" in r2.scrub_text(text)

    # ------------------------------------------------------------------
    # H3: quoted body values are redacted
    # ------------------------------------------------------------------

    def test_scrub_text_quoted_values(self) -> None:
        r = PIIRedactionProcessor()
        # double-quoted
        assert r.scrub_text('token="abc123xyz"') == 'token=' + self.REDACTED
        # single-quoted
        assert r.scrub_text("password='secret'") == "password=" + self.REDACTED
        # unquoted
        assert r.scrub_text("token=x123") == "token=" + self.REDACTED

    # ------------------------------------------------------------------
    # I1: scrub_dict defaults to scrub_strings=False for structured attrs
    # ------------------------------------------------------------------

    def test_scrub_dict_default_no_string_scrub(self) -> None:
        r = PIIRedactionProcessor()
        data = {"url.full": "https://api.example.com/u?ref=US12ABCDE&next=/home"}
        assert r.scrub_dict(data)["url.full"] == data["url.full"]

    def test_scrub_dict_scrubs_strings_when_enabled(self) -> None:
        r = PIIRedactionProcessor()
        result = r.scrub_dict(
            {"msg": "token=abc123", "status": "ok"}, scrub_strings=True
        )
        assert result["msg"] == "token=" + self.REDACTED
        assert result["status"] == "ok"

    def test_scrub_dict_respects_scrub_strings_flag(self) -> None:
        r = PIIRedactionProcessor()
        result = r.scrub_dict({"msg": "token=abc123"}, scrub_strings=False)
        assert result["msg"] == "token=abc123"

    def test_scrub_dict_scrubs_strings_inside_lists(self) -> None:
        r = PIIRedactionProcessor()
        result = r.scrub_dict({"tags": ["token=abc", "ok"]}, scrub_strings=True)
        assert result["tags"] == ["token=" + self.REDACTED, "ok"]

    # ------------------------------------------------------------------
    # I2: 3-group user shape patterns redact whole match correctly
    # ------------------------------------------------------------------

    def test_three_group_shape_pattern_preserved_separators(self) -> None:
        custom = re.compile(r"(CUST)-(\d+)-(\w+)")
        r = PIIRedactionProcessor(extra_body_patterns=(custom,))
        expected = "order " + self.REDACTED + " confirmed"
        assert r.scrub_text("order CUST-123-ABC confirmed") == expected

    # ------------------------------------------------------------------
    # I3: IBAN regex tightened
    # ------------------------------------------------------------------

    def test_iban_tightening(self) -> None:
        r = PIIRedactionProcessor()
        assert self.REDACTED not in r.scrub_text("ref=US12ABCDE")
        # Use an obviously synthetic IBAN (0000… prefix) so secret-scanning
        # tools do not flag it as a live credential.
        assert self.REDACTED in r.scrub_text("ac=PT50 0000 0000 0000 0000 0000 0")

    # ------------------------------------------------------------------
    # I4: bare address term no longer hits OTEL network semconv
    # ------------------------------------------------------------------

    def test_network_addresses_preserved(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("network.peer.address", "10.0.0.1") == "10.0.0.1"
        assert r.scrub_value("network.local.address", "192.168.1.5") == "192.168.1.5"
        assert r.scrub_value("source.address", "10.0.0.2") == "10.0.0.2"
        assert r.scrub_value("destination.address", "1.1.1.1") == "1.1.1.1"

    def test_pii_address_terms_still_redacted(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("street_address", "123 Main St") == self.REDACTED
        assert r.scrub_value("home_address", "123 Home St") == self.REDACTED
        assert r.scrub_value("billing_address", "10 Bill St") == self.REDACTED
        assert r.scrub_value("postal_address", "Post Office") == self.REDACTED

    # ------------------------------------------------------------------
    # I5: KVP lookahead handles & (URL query separator)
    # ------------------------------------------------------------------

    def test_scrub_text_ampersand_boundary(self) -> None:
        r = PIIRedactionProcessor()
        result = r.scrub_text("email=a@b.com&token=xyz&ok=true")
        assert self.REDACTED in result
        assert "a@b.com" not in result
        assert "xyz" not in result
        assert "ok=true" in result

    # ------------------------------------------------------------------
    # I6: empty KVP value does not emit false signal
    # ------------------------------------------------------------------

    def test_empty_kvp_value_unchanged(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_text("token=") == "token="
        assert r.scrub_text("password=") == "password="

    def test_non_empty_kvp_value_redacted(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_text("token=x") == "token=" + self.REDACTED
        assert r.scrub_text("password='abc'") == "password=" + self.REDACTED

    # ------------------------------------------------------------------
    # K1: JSON-string log bodies redacted (key + optional quote before delim)
    # ------------------------------------------------------------------

    def test_scrub_text_json_string_body(self) -> None:
        r = PIIRedactionProcessor()
        assert self.REDACTED in r.scrub_text('{"password": "abc123"}')
        assert self.REDACTED in r.scrub_text('{"token":"xyz"}')
        assert self.REDACTED in r.scrub_text("{'api_key': 'k-secret'}")
        assert "abc123" not in r.scrub_text('{"password": "abc123"}')
        assert "xyz" not in r.scrub_text('{"token":"xyz"}')
        assert "k-secret" not in r.scrub_text("{'api_key': 'k-secret'}")
        # non-secret JSON should pass untouched
        assert r.scrub_text('{"status": "ok"}') == '{"status": "ok"}'

    # ------------------------------------------------------------------
    # K2: api_key shape pattern no longer corrupts JSON output
    # ------------------------------------------------------------------

    def test_api_key_json_not_corrupted(self) -> None:
        r = PIIRedactionProcessor()
        result = r.scrub_text("{'api_key': 'k-secret-value'}")
        assert "k-secret-value" not in result
        assert self.REDACTED in result
        # output should still be valid-ish (no orphaned fragments)
        assert "' '" not in result

    def test_bearer_still_redacted(self) -> None:
        r = PIIRedactionProcessor()
        result = r.scrub_text("Authorization: Bearer eyJhbG.eyJzdWI.SflKxw")
        assert "eyJhbG" not in result
        assert self.REDACTED in result

    # ------------------------------------------------------------------
    # K4: token_type safe
    # ------------------------------------------------------------------

    def test_token_type_preserved(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("token_type", "bearer") == "bearer"
        assert r.scrub_value("access_token", "abc") == self.REDACTED

    # ------------------------------------------------------------------
    # H2: expanded PII terms are redacted; common safe keys preserved
    # ------------------------------------------------------------------

    def test_pii_terms_full_name_redacted(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("full_name", "Alice") == self.REDACTED
        assert r.scrub_value("fullName", "Alice") == self.REDACTED

    def test_pii_terms_address_redacted(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("street_address", "123 Main St") == self.REDACTED
        assert r.scrub_value("home_address", "123 Main") == self.REDACTED

    def test_pii_terms_dob_ip_passport_redacted(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("dob", "1990-01-01") == self.REDACTED
        assert r.scrub_value("ip_address", "192.168.1.1") == self.REDACTED
        assert r.scrub_value("passport", "ABC123") == self.REDACTED

    def test_pii_nif_national_id_redacted(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("nif", "123456789") == self.REDACTED
        assert r.scrub_value("national_id", "PT123456") == self.REDACTED

    def test_service_name_preserved(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("service_name", "my-service") == "my-service"
        assert r.scrub_value("server.address", "1.2.3.4") == "1.2.3.4"
        assert r.scrub_value("client.address", "1.2.3.4") == "1.2.3.4"
        assert r.scrub_value("network.peer.address", "10.0.0.1") == "10.0.0.1"
        assert r.scrub_value("source.address", "10.0.0.2") == "10.0.0.2"

    def test_username_redacted_author_preserved(self) -> None:
        r = PIIRedactionProcessor()
        assert r.scrub_value("username", "alice") == self.REDACTED
        assert r.scrub_value("user_name", "alice") == self.REDACTED
        assert r.scrub_value("author", "Bob") == "Bob"
        assert r.scrub_value("authorization", "bear") == self.REDACTED

    # ------------------------------------------------------------------
    # L1: plain KVP value must not truncate at first whitespace
    # ------------------------------------------------------------------

    def test_l1_multiword_value_not_truncated(self) -> None:
        r = PIIRedactionProcessor()
        secret = "Bearer " + "a" * 6 + "1" * 3
        result = r.scrub_text("token: " + secret + " trailing")
        assert result == "token: " + self.REDACTED
        assert "a" * 6 not in result

    # ------------------------------------------------------------------
    # L2: nested JSON object under a sensitive outer key must not corrupt;
    # the inner sensitive key is redacted independently.
    # ------------------------------------------------------------------

    def test_l2_nested_json_object_value(self) -> None:
        r = PIIRedactionProcessor()
        inner = "n" * 9
        text = '{"auth": {"secret": "' + inner + '"}}'
        result = r.scrub_text(text)
        assert result == '{"auth": {"secret": "' + self.REDACTED + '"}}'
        assert inner not in result

    # ------------------------------------------------------------------
    # L3: JSON string bodies stay structurally valid (quotes/braces intact)
    # ------------------------------------------------------------------

    def test_l3_json_double_quoted_structure_preserved(self) -> None:
        r = PIIRedactionProcessor()
        val = "h" * 5 + "2" * 5
        text = '{"password": "' + val + '"}'
        assert r.scrub_text(text) == '{"password": "' + self.REDACTED + '"}'

    def test_l3_json_single_quoted_structure_preserved(self) -> None:
        r = PIIRedactionProcessor()
        val = "h" * 5 + "2" * 5
        text = "{'password': '" + val + "'}"
        assert r.scrub_text(text) == "{'password': '" + self.REDACTED + "'}"

    def test_l3_json_no_space_after_colon(self) -> None:
        r = PIIRedactionProcessor()
        text = '{"token":"' + "z" * 8 + '"}'
        assert r.scrub_text(text) == '{"token": "' + self.REDACTED + '"}'

    def test_l3_json_numeric_value_redacted(self) -> None:
        # Regression: the JSON number/literal branch was previously dead
        # due to double-escaped \\d; numeric secrets must be redacted.
        r = PIIRedactionProcessor()
        assert "123456789" not in r.scrub_text('{"ssn": 123456789}')
        assert self.REDACTED in r.scrub_text('{"ssn": 123456789}')
        assert self.REDACTED in r.scrub_text('{"cvv": 123}')

    # ------------------------------------------------------------------
    # Idempotency: scrubbing already-scrubbed text must be a no-op
    # ------------------------------------------------------------------

    def test_scrub_text_is_idempotent(self) -> None:
        r = PIIRedactionProcessor()
        samples = [
            "email=a@b.com&token=" + "x" * 6 + "&ok=true",
            "Authorization: Bearer eyJa.eyJb.sig",
            "token: Bearer " + "a" * 6 + " tail",
            '{"password": "' + "p" * 8 + '"}',
            "user=alice password=" + "s" * 6 + " role=admin",
        ]
        for s in samples:
            once = r.scrub_text(s)
            assert r.scrub_text(once) == once, f"not idempotent: {s!r}"

    # ------------------------------------------------------------------
    # No doubled placeholders when shape + KVP both apply
    # ------------------------------------------------------------------

    def test_no_doubled_placeholder_bearer_jwt(self) -> None:
        r = PIIRedactionProcessor()
        result = r.scrub_text("Authorization: Bearer eyJa.eyJb.sig")
        assert result.count(self.REDACTED) == 1
        assert result == "Authorization: " + self.REDACTED

    def test_no_doubled_placeholder_url_query(self) -> None:
        r = PIIRedactionProcessor()
        result = r.scrub_text("email=a@b.com&token=" + "x" * 6 + "&ok=true")
        assert "]]" not in result
        expected = (
            "email=" + self.REDACTED + "&token=" + self.REDACTED + "&ok=true"
        )
        assert result == expected

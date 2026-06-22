"""Tests for _models.py."""

from __future__ import annotations

import pytest

from create_new_rc._models import parse_tag


class TestParseTag:
    """Tests for parse_tag()."""

    @pytest.mark.parametrize(
        ("tag", "expected_year", "expected_minor", "expected_patch"),
        [
            ("v2026.2.0-rc3", 2026, 2, 0),
            ("v2025.1.0-rc0", 2025, 1, 0),
            ("v2026.10.5-rc1", 2026, 10, 5),
        ],
    )
    def test_parse_regular_rc_versions(
        self,
        tag: str,
        expected_year: int,
        expected_minor: int,
        expected_patch: int,
    ) -> None:
        """Parse regular RC tags with various versions."""
        parsed_tag = parse_tag(tag)
        assert parsed_tag is not None
        assert parsed_tag.year == expected_year
        assert parsed_tag.minor == expected_minor
        assert parsed_tag.patch == expected_patch
        assert parsed_tag.hotfix is None

    def test_parse_regular_rc_properties(self) -> None:
        """Regular RC tag properties."""
        parsed_tag = parse_tag("v2026.2.0-rc3")
        assert parsed_tag is not None
        assert parsed_tag.rc == 3
        assert parsed_tag.base_version == "v2026.2.0"
        assert parsed_tag.base_tuple == (2026, 2, 0)

    @pytest.mark.parametrize(
        ("tag", "expected_hotfix", "expected_rc"),
        [
            ("v2026.2.0-h1-rc3", 1, 3),
            ("v2026.2.0-h2-rc5", 2, 5),
        ],
    )
    def test_parse_hotfix_rc_versions(
        self,
        tag: str,
        expected_hotfix: int,
        expected_rc: int,
    ) -> None:
        """Parse hotfix RC tags with various hotfix and RC numbers."""
        parsed_tag = parse_tag(tag)
        assert parsed_tag is not None
        assert parsed_tag.hotfix == expected_hotfix
        assert parsed_tag.rc == expected_rc

    @pytest.mark.parametrize(
        "invalid_tag",
        [
            "v2026.2.0",
            "release-v2026.2.0",
            "v2026.2.0-rc",
            "",
            "random-tag",
        ],
    )
    def test_parse_invalid_tag(self, invalid_tag: str) -> None:
        """Invalid tags return None."""
        assert parse_tag(invalid_tag) is None

    def test_parse_tag_raw_preserved(self) -> None:
        """The raw tag string is preserved in ParsedTag."""
        raw_tag = "v2026.2.0-rc3"
        parsed_tag = parse_tag(raw_tag)
        assert parsed_tag is not None
        assert parsed_tag.raw == raw_tag

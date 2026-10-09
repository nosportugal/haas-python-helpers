"""Tests for _version.py."""

from __future__ import annotations

import pytest

from create_new_rc._models import parse_tag
from create_new_rc._version import (
    bump_minor,
    compute_next_hotfix,
    compute_next_regular,
    latest_base_version_from_tags,
    parse_base_version,
)

_BASE_V2026_2_0 = "v2026.2.0"
_BASE_V2026_2_0_RC1 = "v2026.2.0-rc1"


class TestParseBaseVersion:
    """Tests for parse_base_version()."""

    @pytest.mark.parametrize(
        ("version_str", "expected_year", "expected_minor", "expected_patch"),
        [
            (_BASE_V2026_2_0, 2026, 2, 0),
            ("v2025.1.0", 2025, 1, 0),
            ("v2026.10.5", 2026, 10, 5),
        ],
    )
    def test_parse_base_version(
        self,
        version_str: str,
        expected_year: int,
        expected_minor: int,
        expected_patch: int,
    ) -> None:
        """Parse valid base versions."""
        parsed = parse_base_version(version_str)
        assert parsed == (expected_year, expected_minor, expected_patch)

    @pytest.mark.parametrize(
        "invalid_version",
        [
            "2026.2.0",  # missing v
            "v2026.2",  # missing patch
            _BASE_V2026_2_0_RC1,  # has rc suffix
        ],
    )
    def test_parse_invalid_base_version(self, invalid_version: str) -> None:
        """Invalid base versions raise ValueError."""
        with pytest.raises(ValueError, match="Invalid base version"):
            parse_base_version(invalid_version)


class TestBumpMinor:
    """Tests for bump_minor()."""

    @pytest.mark.parametrize(
        ("input_version", "expected_output"),
        [
            ("v2026.1.0", _BASE_V2026_2_0),
            ("v2026.2.5", "v2026.3.0"),
            ("v2026.99.0", "v2026.100.0"),
        ],
    )
    def test_bump_minor(
        self,
        input_version: str,
        expected_output: str,
    ) -> None:
        """bump_minor increments the minor version and resets patch."""
        bumped = bump_minor(input_version)
        assert bumped == expected_output


class TestLatestBaseVersionFromTags:
    """Tests for latest_base_version_from_tags()."""

    def test_empty_tags(self) -> None:
        """Empty tags list returns None."""
        assert latest_base_version_from_tags([]) is None

    def test_single_tag(self) -> None:
        """Single tag returns that tag's base version."""
        tags = [parse_tag("v2026.2.0-rc1")]
        tags = [tag for tag in tags if tag is not None]
        assert latest_base_version_from_tags(tags) == "v2026.2.0"

    def test_multiple_tags_picks_latest(self) -> None:
        """Multiple tags returns the maximum base version."""
        tag_strings = [
            "v2026.1.0-rc1",
            "v2026.3.0-rc1",
            "v2026.2.0-rc1",
        ]
        tags = [parse_tag(tag_str) for tag_str in tag_strings]
        tags = [tag for tag in tags if tag is not None]
        assert latest_base_version_from_tags(tags) == "v2026.3.0"


class TestComputeNextRegular:
    """Tests for compute_next_regular()."""

    def test_no_tags_explicit_base(self) -> None:
        """With explicit base version and no tags."""
        next_tag, base_version = compute_next_regular([], "v2026.2.0")
        assert next_tag == "v2026.2.0-rc0"
        assert base_version == "v2026.2.0"

    def test_existing_tags_no_explicit_base(self) -> None:
        """With existing tags, computes next RC for the latest base."""
        tag_strings = [
            "v2026.1.0-rc1",
            "v2026.1.0-rc2",
            "v2026.2.0-rc0",
        ]
        tags = [parse_tag(tag_str) for tag_str in tag_strings]
        tags = [tag for tag in tags if tag is not None]
        next_tag, base_version = compute_next_regular(tags, None)
        assert base_version == "v2026.2.0"
        assert next_tag == "v2026.2.0-rc1"

    def test_explicit_base_overrides_tags(self) -> None:
        """Explicit base version overrides inferred base."""
        tag_strings = [
            "v2026.2.0-rc1",
            "v2026.2.0-rc2",
        ]
        tags = [parse_tag(tag_str) for tag_str in tag_strings]
        tags = [tag for tag in tags if tag is not None]
        next_tag, base_version = compute_next_regular(tags, "v2026.1.0")
        assert base_version == "v2026.1.0"
        assert next_tag == "v2026.1.0-rc0"


class TestComputeNextHotfix:
    """Tests for compute_next_hotfix()."""

    def test_no_tags_explicit_base(self) -> None:
        """First hotfix for a base version."""
        next_tag, base_version = compute_next_hotfix([], "v2026.2.0")
        assert next_tag == "v2026.2.0-h1-rc0"
        assert base_version == "v2026.2.0"

    def test_existing_hotfix_tags(self) -> None:
        """Compute next hotfix when hotfixes exist."""
        tag_strings = [
            "v2026.2.0-h1-rc0",
            "v2026.2.0-h1-rc1",
            "v2026.2.0-h2-rc0",
        ]
        tags = [parse_tag(tag_str) for tag_str in tag_strings]
        tags = [tag for tag in tags if tag is not None]
        next_tag, base_version = compute_next_hotfix(tags, "v2026.2.0")
        assert base_version == "v2026.2.0"
        assert next_tag == "v2026.2.0-h2-rc1"

    def test_mixed_regular_and_hotfix(self) -> None:
        """With both regular and hotfix tags."""
        tag_strings = [
            "v2026.1.0-rc1",
            "v2026.2.0-h1-rc0",
        ]
        tags = [parse_tag(tag_str) for tag_str in tag_strings]
        tags = [tag for tag in tags if tag is not None]
        next_tag, base_version = compute_next_hotfix(tags, None)
        assert base_version == "v2026.2.0"
        assert next_tag == "v2026.2.0-h1-rc1"

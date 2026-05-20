"""Tests for CLI argument parsing."""

from __future__ import annotations

import pytest

from create_new_rc.cli import parse_args

_RC_TYPE_REGULAR = "regular"
_RC_TYPE_HOTFIX = "hotfix"
_BASE_VERSION = "v2026.2.0"
_REPO = "owner/repo"


class TestParseArgs:
    """Tests for parse_args()."""

    def test_default_args(self) -> None:
        """Default arguments."""
        parsed_args = parse_args([])
        assert parsed_args.rc_type == _RC_TYPE_REGULAR
        assert parsed_args.base_version is None
        assert parsed_args.repo is None
        assert parsed_args.dry_run is False

    @pytest.mark.parametrize(
        ("arg_list", "expected_rc_type"),
        [
            (["--type", _RC_TYPE_REGULAR], _RC_TYPE_REGULAR),
            (["--type", _RC_TYPE_HOTFIX], _RC_TYPE_HOTFIX),
        ],
    )
    def test_parse_type(self, arg_list: list[str], expected_rc_type: str) -> None:
        """Parse --type argument."""
        parsed_args = parse_args(arg_list)
        assert parsed_args.rc_type == expected_rc_type

    def test_parse_base_version(self) -> None:
        """Parse --base-version."""
        parsed_args = parse_args(["--base-version", _BASE_VERSION])
        assert parsed_args.base_version == _BASE_VERSION

    def test_parse_repo(self) -> None:
        """Parse --repo."""
        parsed_args = parse_args(["--repo", _REPO])
        assert parsed_args.repo == _REPO

    def test_parse_dry_run(self) -> None:
        """Parse --dry-run."""
        parsed_args = parse_args(["--dry-run"])
        assert parsed_args.dry_run is True

    def test_combined_args(self) -> None:
        """Parse multiple arguments together."""
        arg_list = [
            "--type",
            _RC_TYPE_HOTFIX,
            "--base-version",
            _BASE_VERSION,
            "--repo",
            _REPO,
            "--dry-run",
        ]
        parsed_args = parse_args(arg_list)
        assert parsed_args.rc_type == _RC_TYPE_HOTFIX
        assert parsed_args.base_version == _BASE_VERSION
        assert parsed_args.repo == _REPO
        assert parsed_args.dry_run is True

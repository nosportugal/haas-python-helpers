from __future__ import annotations

import argparse

import pytest

from sync_confluence.cli import parse_args, validate_args


class TestParseArgs:
    """Tests for parse_args()."""

    def test_all_required_flags(self):
        args = parse_args(
            [
                "--url",
                "https://acme.atlassian.net",
                "--email",
                "user@acme.com",
                "--token",
                "secret",
                "--space",
                "DOCS",
                "--parent-id",
                "12345",
            ]
        )
        assert args.url == "https://acme.atlassian.net"
        assert args.email == "user@acme.com"
        assert args.token == "secret"
        assert args.space == "DOCS"
        assert args.parent_id == "12345"

    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
        args = parse_args([])
        assert args.dry_run is False
        assert args.no_root is False
        assert args.git_ref == "main"
        assert args.log_level == "INFO"

    def test_dry_run_flag(self):
        args = parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_docs_files_flag(self):
        args = parse_args(["--docs-files", "a.md", "b.md"])
        assert args.docs_files == ["a.md", "b.md"]

    def test_no_root_flag(self):
        args = parse_args(["--no-root"])
        assert args.no_root is True


class TestValidateArgs:
    """Tests for validate_args()."""

    def _make_args(self, **overrides):
        defaults = {
            "url": "https://acme.atlassian.net",
            "email": "user@acme.com",
            "token": "secret",
            "space": "DOCS",
            "parent_id": "12345",
            "no_root": False,
            "root_parent": None,
            "root_title": None,
            "docs_dir": None,
            "docs_files": None,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_valid_args_pass(self):
        args = self._make_args()
        # Should not raise or exit
        validate_args(args)

    def test_missing_url_exits(self):
        args = self._make_args(url=None)
        with pytest.raises(SystemExit) as exc_info:
            validate_args(args)
        assert exc_info.value.code == 2

    def test_missing_token_exits(self):
        args = self._make_args(token=None)
        with pytest.raises(SystemExit) as exc_info:
            validate_args(args)
        assert exc_info.value.code == 2

    def test_mutually_exclusive_root_opts(self):
        args = self._make_args(no_root=True, root_title="Title")
        with pytest.raises(SystemExit) as exc_info:
            validate_args(args)
        assert exc_info.value.code == 2

    def test_mutually_exclusive_docs_dir_and_files(self):
        args = self._make_args(docs_dir="docs", docs_files=["a.md"])
        with pytest.raises(SystemExit) as exc_info:
            validate_args(args)
        assert exc_info.value.code == 2

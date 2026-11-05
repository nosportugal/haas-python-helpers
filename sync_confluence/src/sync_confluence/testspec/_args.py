"""Argument parsing for ``sync-confluence-testspec``."""

from __future__ import annotations

import argparse
from typing import Optional

from sync_confluence.cli._args import _add_connection_args, _add_meta_args
from sync_confluence.cli._env import _env

REQUIRED_ARGS = (
    ("url", "--url / CONFLUENCE_URL"),
    ("email", "--email / CONFLUENCE_EMAIL"),
    ("token", "--token / CONFLUENCE_API_TOKEN"),
    ("space", "--space / CONFLUENCE_SPACE_KEY"),
    ("parent_id", "--parent-id / CONFLUENCE_PARENT_PAGE_ID"),
    ("xlsx", "--xlsx / TESTSPEC_XLSX"),
)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync a test-specification workbook (.xlsx) to Confluence Cloud.",
    )
    _add_connection_args(parser)
    parser.add_argument(
        "--xlsx",
        default=_env("TESTSPEC_XLSX"),
        help="Path to the test-specification workbook (env: TESTSPEC_XLSX).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview pages that would be created/updated/deleted.",
    )
    _add_meta_args(parser)
    return parser.parse_args(argv)


def missing_required(args: argparse.Namespace) -> list[str]:
    """Return the labels of required options that are not set."""
    return [label for attr, label in REQUIRED_ARGS if not getattr(args, attr)]

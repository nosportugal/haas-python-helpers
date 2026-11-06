"""Argument parsing for ``sync-confluence-testspec``."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from sync_confluence.confluence.sync_cli import (
    add_confluence_connection_args,
    add_page_metadata_args,
    env_or_default,
)
from sync_confluence.testspec._suite import suite_from_filename, validate_suite_id

_TRUTHY_ENV_VALUES = ("1", "true", "yes")
REQUIRED_ARGS = (
    ("url", "--url / CONFLUENCE_URL"),
    ("email", "--email / CONFLUENCE_EMAIL"),
    ("token", "--token / CONFLUENCE_API_TOKEN"),
    ("space", "--space / CONFLUENCE_SPACE_KEY"),
    ("parent_id", "--parent-id / CONFLUENCE_PARENT_PAGE_ID"),
    ("xlsx", "--xlsx / TESTSPEC_XLSX"),
)


def parse_testspec_sync_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse ``sync-confluence-testspec`` command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Sync a test-specification workbook (.xlsx) to Confluence Cloud.",
    )
    add_confluence_connection_args(parser)
    parser.add_argument(
        "--xlsx",
        default=env_or_default("TESTSPEC_XLSX"),
        help="Path to the test-specification workbook (env: TESTSPEC_XLSX).",
    )
    parser.add_argument(
        "--suite",
        default=env_or_default("TESTSPEC_SUITE"),
        help=(
            "Suite ID added to folder and page titles (Confluence titles are "
            "unique per space) and used to scope orphan cleanup to this "
            "workbook's pages, e.g. HAAS-L3VPN-CISCO. Defaults to the ID at "
            "the start of the workbook file name, "
            "<ID>[__<description>].xlsx (env: TESTSPEC_SUITE)."
        ),
    )
    parser.add_argument(
        "--format-json",
        action="store_true",
        default=(env_or_default("TESTSPEC_FORMAT_JSON") or "").casefold()
        in _TRUTHY_ENV_VALUES,
        help=(
            "Pretty-print valid JSON in columns headed 'JSON'. Off by default "
            "because reformatting can change a cell (duplicate keys are "
            "dropped, 1.50 becomes 1.5). Invalid JSON is always shown "
            "unchanged (env: TESTSPEC_FORMAT_JSON=true)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview pages that would be created/updated/deleted.",
    )
    add_page_metadata_args(parser)
    return parser.parse_args(argv)


def missing_required(args: argparse.Namespace) -> list[str]:
    """Return the labels of required options that are not set."""
    return [label for attr, label in REQUIRED_ARGS if not getattr(args, attr)]


def resolve_suite(args: argparse.Namespace) -> str:
    """Return the suite ID: ``--suite`` or the one in the workbook file name.

    Both go through the same check, so ``--suite`` cannot bypass the rule.
    """
    if args.suite:
        return validate_suite_id(args.suite)
    return suite_from_filename(Path(args.xlsx).name)

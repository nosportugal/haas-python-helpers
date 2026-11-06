"""Argument parsing and validation for the CLI."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from sync_confluence.confluence.sync_cli import (
    add_confluence_connection_args,
    add_page_metadata_args,
    env_or_default,
)

log = logging.getLogger(__name__)

_STORE_TRUE = "store_true"


def _add_docs_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--docs-dir",
        default=env_or_default("DOCS_DIR"),
        help=(
            "Path to the docs directory (env: DOCS_DIR). "
            "Auto-detected from common names (docs/, documentation/, doc/) "
            "when not set. Mutually exclusive with --docs-files."
        ),
    )
    parser.add_argument(
        "--docs-files",
        nargs="+",
        metavar="FILE",
        help=(
            "One or more Markdown files to sync as leaf pages directly under "
            "the parent. Mutually exclusive with --docs-dir."
        ),
    )
    parser.add_argument(
        "--root-title",
        default=env_or_default("CONFLUENCE_ROOT_TITLE"),
        help=(
            "Title for the root page.  Defaults to the first H1 heading "
            "in docs/README.md (env: CONFLUENCE_ROOT_TITLE)."
        ),
    )


def _add_sync_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--git-ref",
        default=env_or_default("GITHUB_REF_NAME", "main"),
        help="Git ref used in GitHub link construction (env: GITHUB_REF_NAME).",
    )
    parser.add_argument(
        "--mermaid-macro",
        default=env_or_default("CONFLUENCE_MERMAID_MACRO"),
        help=(
            "Confluence macro name for Mermaid diagrams.  "
            "Omit to render Mermaid as a code block "
            "(env: CONFLUENCE_MERMAID_MACRO)."
        ),
    )
    parser.add_argument(
        "--mmdc-path",
        default=env_or_default("MMDC_PATH"),
        help=(
            "Path to the mmdc binary.  Defaults to 'mmdc' found on $PATH "
            "(env: MMDC_PATH)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action=_STORE_TRUE,
        help="Preview pages that would be created/updated/deleted.",
    )
    parser.add_argument(
        "--no-root",
        action=_STORE_TRUE,
        help=(
            "Sync all docs directly under --parent-id without creating an "
            "intermediate root page from docs/README.md. "
            "Mutually exclusive with --root-parent and --root-title."
        ),
    )
    parser.add_argument(
        "--root-parent",
        default=env_or_default("CONFLUENCE_ROOT_PARENT"),
        help=(
            "Title of a container page to find or create under --parent-id. "
            "All docs are synced directly under this container. "
            "Mutually exclusive with --no-root and --root-title "
            "(env: CONFLUENCE_ROOT_PARENT)."
        ),
    )


def parse_markdown_sync_args(
    argv: Optional[list[str]] = None,
) -> argparse.Namespace:
    """Parse ``sync-confluence-markdown`` command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Sync a docs/ tree to Confluence Cloud.",
    )
    add_confluence_connection_args(parser)
    _add_docs_args(parser)
    _add_sync_args(parser)
    add_page_metadata_args(parser)
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    missing = []
    for attr, label in (
        ("url", "--url / CONFLUENCE_URL"),
        ("email", "--email / CONFLUENCE_EMAIL"),
        ("token", "--token / CONFLUENCE_API_TOKEN"),
        ("space", "--space / CONFLUENCE_SPACE_KEY"),
        ("parent_id", "--parent-id / CONFLUENCE_PARENT_PAGE_ID"),
    ):
        if not getattr(args, attr, None):
            missing.append(label)
    if missing:
        log.error("Missing required configuration: %s", ", ".join(missing))
        sys.exit(2)

    root_opts = [
        opt_name
        for opt_name in ("no_root", "root_parent", "root_title")
        if getattr(args, opt_name, None)
    ]
    if len(root_opts) > 1:
        log.error(
            "--no-root, --root-parent, and --root-title are mutually exclusive; "
            "provide at most one."
        )
        sys.exit(2)

    if args.docs_dir and getattr(args, "docs_files", None):
        log.error("--docs-dir and --docs-files are mutually exclusive.")
        sys.exit(2)

    if args.page_width not in (None, "full-width", "default"):
        log.error(
            "Invalid --page-width '%s'; valid values: full-width, default",
            args.page_width,
        )
        sys.exit(2)

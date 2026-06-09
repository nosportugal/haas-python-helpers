"""Argument parsing and validation for the CLI."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from sync_confluence.cli._env import _env

log = logging.getLogger(__name__)

_STORE_TRUE = "store_true"


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--url",
        default=_env("CONFLUENCE_URL"),
        help="Confluence base URL (env: CONFLUENCE_URL).",
    )
    parser.add_argument(
        "--email",
        default=_env("CONFLUENCE_EMAIL"),
        help="Atlassian account email (env: CONFLUENCE_EMAIL).",
    )
    parser.add_argument(
        "--token",
        default=_env("CONFLUENCE_API_TOKEN"),
        help="Atlassian API token (env: CONFLUENCE_API_TOKEN).",
    )
    parser.add_argument(
        "--space",
        default=_env("CONFLUENCE_SPACE_KEY"),
        help="Confluence space key (env: CONFLUENCE_SPACE_KEY).",
    )
    parser.add_argument(
        "--parent-id",
        default=_env("CONFLUENCE_PARENT_PAGE_ID"),
        help="Numeric ID of the parent page (env: CONFLUENCE_PARENT_PAGE_ID).",
    )


def _add_docs_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--docs-dir",
        default=_env("DOCS_DIR"),
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
        default=_env("CONFLUENCE_ROOT_TITLE"),
        help=(
            "Title for the root page.  Defaults to the first H1 heading "
            "in docs/README.md (env: CONFLUENCE_ROOT_TITLE)."
        ),
    )


def _add_sync_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--git-ref",
        default=_env("GITHUB_REF_NAME", "main"),
        help="Git ref used in GitHub link construction (env: GITHUB_REF_NAME).",
    )
    parser.add_argument(
        "--mermaid-macro",
        default=_env("CONFLUENCE_MERMAID_MACRO"),
        help=(
            "Confluence macro name for Mermaid diagrams.  "
            "Omit to render Mermaid as a code block "
            "(env: CONFLUENCE_MERMAID_MACRO)."
        ),
    )
    parser.add_argument(
        "--mmdc-path",
        default=_env("MMDC_PATH"),
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
        default=_env("CONFLUENCE_ROOT_PARENT"),
        help=(
            "Title of a container page to find or create under --parent-id. "
            "All docs are synced directly under this container. "
            "Mutually exclusive with --no-root and --root-title "
            "(env: CONFLUENCE_ROOT_PARENT)."
        ),
    )


def _add_meta_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--managed-by",
        default=_env("CONFLUENCE_MANAGED_BY"),
        help=(
            "Confluence label applied to every page created or updated by this sync. "
            "Only pages carrying this label are eligible for orphan removal, "
            "preventing accidental deletion of unrelated pages. "
            "Auto-derived from the git repository name when not set "
            "(e.g. 'managed-by-a3-e2e'). "
            "(env: CONFLUENCE_MANAGED_BY)"
        ),
    )
    parser.add_argument(
        "--log-level",
        default=_env("LOG_LEVEL", "INFO"),
        help="Logging verbosity (env: LOG_LEVEL, default: INFO).",
    )
    parser.add_argument(
        "--page-width",
        default=_env("CONFLUENCE_PAGE_WIDTH"),
        choices=["full-width", "default"],
        help=(
            "Display width for every synced page. "
            "'full-width' renders content across the full browser width; "
            "'default' uses the standard Confluence narrow layout. "
            "Omit to leave page widths unchanged "
            "(env: CONFLUENCE_PAGE_WIDTH)."
        ),
    )
    parser.add_argument(
        "--generated-by",
        default=_env("CONFLUENCE_GENERATED_BY"),
        help=(
            "Banner text prepended to every page as an info panel. Supports "
            "%%{filepath}, %%{filename}, %%{filedir} and %%{filestem} "
            "placeholders. Defaults to a standard auto-generated notice "
            "(env: CONFLUENCE_GENERATED_BY)."
        ),
    )
    parser.add_argument(
        "--no-generated-by",
        action=_STORE_TRUE,
        help="Do not prepend the auto-generated banner to pages.",
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync a docs/ tree to Confluence Cloud.",
    )
    _add_connection_args(parser)
    _add_docs_args(parser)
    _add_sync_args(parser)
    _add_meta_args(parser)
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

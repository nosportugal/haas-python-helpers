"""Command-line options shared by every sync front end."""

from __future__ import annotations

import argparse

from sync_confluence.confluence.sync_cli._env_defaults import env_or_default


def add_confluence_connection_args(parser: argparse.ArgumentParser) -> None:
    """Add the Confluence connection options (url, email, token, space, parent id)."""
    parser.add_argument(
        "--url",
        default=env_or_default("CONFLUENCE_URL"),
        help="Confluence base URL (env: CONFLUENCE_URL).",
    )
    parser.add_argument(
        "--email",
        default=env_or_default("CONFLUENCE_EMAIL"),
        help="Atlassian account email (env: CONFLUENCE_EMAIL).",
    )
    parser.add_argument(
        "--token",
        default=env_or_default("CONFLUENCE_API_TOKEN"),
        help="Atlassian API token (env: CONFLUENCE_API_TOKEN).",
    )
    parser.add_argument(
        "--space",
        default=env_or_default("CONFLUENCE_SPACE_KEY"),
        help="Confluence space key (env: CONFLUENCE_SPACE_KEY).",
    )
    parser.add_argument(
        "--parent-id",
        default=env_or_default("CONFLUENCE_PARENT_PAGE_ID"),
        help="Numeric ID of the parent page (env: CONFLUENCE_PARENT_PAGE_ID).",
    )


def add_page_metadata_args(parser: argparse.ArgumentParser) -> None:
    """Add managed-by label, log level, page width and generated-by banner options."""
    parser.add_argument(
        "--managed-by",
        default=env_or_default("CONFLUENCE_MANAGED_BY"),
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
        default=env_or_default("LOG_LEVEL", "INFO"),
        help="Logging verbosity (env: LOG_LEVEL, default: INFO).",
    )
    parser.add_argument(
        "--page-width",
        default=env_or_default("CONFLUENCE_PAGE_WIDTH"),
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
        default=env_or_default("CONFLUENCE_GENERATED_BY"),
        help=(
            "Banner text prepended to every page as an info panel. Supports "
            "%%{filepath}, %%{filename}, %%{filedir} and %%{filestem} "
            "placeholders. Defaults to a standard auto-generated notice "
            "(env: CONFLUENCE_GENERATED_BY)."
        ),
    )
    parser.add_argument(
        "--no-generated-by",
        action="store_true",
        help="Do not prepend the auto-generated banner to pages.",
    )
